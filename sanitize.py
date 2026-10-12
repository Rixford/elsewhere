"""Convert model output into a scriptless document with a tiny trusted controller."""
import html
import re
import secrets
import xml.etree.ElementTree as ET
from pathlib import Path

import html5lib
import tinycss2

HTML_TAGS = set('html head body title style main header footer nav section article aside div span p a button h1 h2 h3 h4 h5 h6 ul ol li dl dt dd strong em b i u s small mark code pre blockquote br hr table thead tbody tfoot tr td th caption colgroup col form label input textarea select option optgroup fieldset legend details summary dialog progress meter figure figcaption time sub sup abbr'.split())
SVG_TAGS = set('svg g path rect circle ellipse line polyline polygon text tspan defs linearGradient radialGradient stop clipPath mask pattern symbol use title desc'.split())
DROP_CONTENT = set('script iframe frame frameset object embed applet noscript template foreignObject animate animateMotion animateTransform set audio video source track canvas math'.lower().split())
ATTRS = set('id class title role tabindex lang dir hidden aria-label aria-labelledby aria-describedby aria-expanded aria-controls aria-hidden aria-live aria-current aria-selected type name value placeholder checked selected disabled required readonly multiple min max step rows cols for colspan rowspan scope open datetime start reversed width height viewbox preserveaspectratio d x y x1 x2 y1 y2 cx cy r rx ry points fill stroke stroke-width stroke-linecap stroke-linejoin opacity fill-opacity stroke-opacity fill-rule clip-rule transform offset stop-color stop-opacity gradientunits gradienttransform patternunits patterntransform clip-path mask text-anchor dominant-baseline font-size font-family font-weight dx dy'.split())

def local_name(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''

def safe_tokens(tokens):
    for token in tokens:
        if token.type == 'error':
            return False
        if token.type == 'url' and not re.fullmatch(r'#[\w:.-]+', token.value):
            return False
        if token.type == 'function':
            if token.lower_name in ('expression', 'image-set', '-webkit-image-set', 'paint', 'src'):
                return False
            if token.lower_name == 'url':
                arg = tinycss2.serialize(token.arguments).strip().strip('\"\'')
                if not re.fullmatch(r'#[\w:.-]+', arg):
                    return False
            if not safe_tokens(token.arguments):
                return False
        if hasattr(token, 'content') and not safe_tokens(token.content):
            return False
    return True

def declarations(text):
    out = []
    for rule in tinycss2.parse_declaration_list(text, skip_comments=True, skip_whitespace=True):
        if rule.type != 'declaration' or rule.lower_name in ('behavior', '-moz-binding'):
            continue
        if safe_tokens(rule.value):
            out.append(rule)
    return tinycss2.serialize(out)

def stylesheet(text):
    out = []
    for rule in tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True):
        if rule.type == 'qualified-rule' and safe_tokens(rule.prelude):
            body = declarations(tinycss2.serialize(rule.content))
            out.append(tinycss2.serialize(rule.prelude) + '{' + body + '}')
        elif rule.type == 'at-rule' and rule.lower_at_keyword in ('media', 'supports', 'keyframes', '-webkit-keyframes', 'container', 'layer') and rule.content is not None and safe_tokens(rule.prelude):
            body = stylesheet(tinycss2.serialize(rule.content))
            out.append('@' + rule.lower_at_keyword + ' ' + tinycss2.serialize(rule.prelude) + '{' + body + '}')
    return '\n'.join(out).replace('</', '< /')

def unwrap_markdown(raw):
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.S).strip()
    match = re.search(r'```(?:html)?\s*([\s\S]*?)```', raw, re.I)
    if match:
        raw = match.group(1)
    if raw.lstrip().startswith('<'):
        return raw
    start = re.search(r'<!doctype\s+html|<html[\s>]|<head[\s>]|<body[\s>]|<style[\s>]|<main[\s>]|<div[\s>]', raw, re.I)
    return raw[start.start():] if start else raw

def sanitize(raw, capability='preview', title_fallback='An imagined place', script_nonce=None):
    if len(raw) > 180_000:
        raise ValueError('The page exceeded the size limit.')
    parser = html5lib.HTMLParser(namespaceHTMLElements=False)
    root = parser.parse(unwrap_markdown(raw))
    if sum(1 for _ in root.iter()) > 3500:
        raise ValueError('The generated page has too many elements.')
    removed = []

    def clean(parent, depth=0):
        if depth > 48:
            raise ValueError('The page has excessive nesting.')
        for child in list(parent):
            if not isinstance(child.tag,str):
                parent.remove(child)
                continue
            tag = local_name(child.tag)
            low = tag.lower()
            if low in DROP_CONTENT or (tag not in HTML_TAGS and tag not in SVG_TAGS):
                # Keep ordinary unknown-tag text, never contents of executable containers.
                if low not in DROP_CONTENT and low not in ('link', 'meta', 'base', 'img') and not child.tag.startswith('{http://www.w3.org/2000/svg}'):
                    text = ''.join(child.itertext())
                    span = ET.Element('span')
                    span.text = text
                    span.tail = child.tail
                    parent.insert(list(parent).index(child), span)
                removed.append(low or 'comment')
                parent.remove(child)
                continue
            old = dict(child.attrib)
            child.attrib.clear()
            for key, value in old.items():
                attr = local_name(key).lower()
                if attr in ('class','id','role','type','data-target','data-filter','aria-controls') and re.fullmatch(r'\\["\'].*\\["\']',value,re.S):
                    value=value[2:-2]
                if attr == 'style':
                    child.set('style', declarations(value))
                elif attr == 'href':
                    if tag in ('use',) and re.fullmatch(r'#[\w:.-]+', value):
                        child.set('href', value)
                    elif tag == 'a':
                        child.set('href', '#')
                        if value.startswith('#'):
                            child.set('data-anchor', value[:200])
                        elif not re.match(r'\s*(javascript|data|file|vbscript|mailto|tel):', value, re.I):
                            child.set('data-intent', value[:500])
                elif attr in ('data-prompt', 'data-intent', 'data-target', 'data-filter', 'data-dialog', 'data-close', 'data-value'):
                    child.set(attr, value[:500])
                elif attr in ATTRS:
                    if attr in ('fill', 'stroke', 'filter', 'clip-path', 'mask') and not safe_tokens(tinycss2.parse_component_value_list(value)):
                        continue
                    if attr == 'type' and tag == 'input' and value.lower() not in ('text', 'search', 'number', 'range', 'checkbox', 'radio', 'email', 'password', 'date', 'color', 'submit', 'button', 'reset'):
                        value = 'text'
                    child.set(key if not key.startswith('{') else attr, value[:2000])
            if tag == 'style':
                child.text = stylesheet(child.text or '')
            if tag == 'form':
                child.set('autocomplete', 'off')
            clean(child, depth+1)

    clean(root)
    head = root.find('head')
    body = root.find('body')
    if head is None or body is None:
        raise ValueError('The model did not produce a page.')
    title_node = head.find('title')
    title = (''.join(title_node.itertext()).strip() if title_node is not None else title_fallback)[:120]
    # Readable body content excludes CSS; use it for copy review and continuity.
    def visible_text(node):
        if local_name(node.tag) not in ('style','script'):
            if node.text:yield node.text
            for child in node:
                yield from visible_text(child)
                if child.tail:yield child.tail
    text = ' '.join(t.strip() for t in visible_text(body)).strip()
    if len(text) < 40:
        raise ValueError('The model produced too little visible content. Try Reimagine.')
    nonce = script_nonce or secrets.token_urlsafe(20)
    csp = f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; img-src 'none'; font-src 'none'; connect-src 'none'; media-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none';"
    meta = ET.Element('meta', {'http-equiv': 'Content-Security-Policy', 'content': csp})
    head.insert(0, meta)
    head.insert(1, ET.Element('meta', {'charset': 'utf-8'}))
    head.insert(2, ET.Element('meta', {'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}))
    base = ET.Element('style')
    head.insert(3,base)
    base.text = '*,*::before,*::after{box-sizing:border-box}html{overflow-wrap:anywhere}body{margin:0}svg{max-width:100%}input,button,select,textarea{font:inherit;min-width:0}button{flex-shrink:0;overflow-wrap:normal}button,a,summary{touch-action:manipulation}button,a{cursor:pointer}:focus-visible{outline:3px solid #787dff;outline-offset:3px}img{display:none} @media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}'
    code = (Path(__file__).parent / 'web' / 'page-controller.js').read_text(encoding='utf-8')
    import json
    script = ET.SubElement(body, 'script', {'nonce': nonce})
    script.text = code.replace('__CAPABILITY__', json.dumps(capability))
    result = '<!doctype html>\n' + html5lib.serialize(root, tree='etree', quote_attr_values='always', omit_optional_tags=False, alphabetical_attributes=True)
    issues = []
    ids = [n.get('id') for n in root.iter() if n.get('id')]
    if len(ids) != len(set(ids)):
        issues.append('Duplicate element IDs may break local interactions.')
    if not any(local_name(n.tag) in ('h1', 'h2') for n in body.iter()):
        issues.append('The page has no heading.')
    return {'html': result, 'title': title or title_fallback, 'text': text[:16000], 'issues': issues, 'removed': sorted(set(removed)), 'parse_errors': len(parser.errors)}
