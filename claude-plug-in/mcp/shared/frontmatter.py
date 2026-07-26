import warnings

import yaml


def parse(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return ({}, text)

    rest = text[4:]
    end = rest.find("\n---\n")

    if end == -1:
        if rest.endswith("\n---"):
            yaml_block = rest[:-4]
            body_raw = ""
        else:
            return ({}, text)
    else:
        yaml_block = rest[:end]
        body_raw = rest[end + 5:]

    try:
        meta = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        warnings.warn("Malformed YAML frontmatter; treating as plain text")
        return ({}, text)

    body = body_raw[1:] if body_raw.startswith("\n") else body_raw
    return (meta, body)


def write(meta: dict, body: str) -> str:
    body = body.replace("\r\n", "\n")
    if not meta:
        return body
    yaml_block = yaml.dump(meta, default_flow_style=False, allow_unicode=True)
    return f"---\n{yaml_block}---\n\n{body}"
