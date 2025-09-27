def _norm_primary(path: str) -> str:
    if not path or path == "/":
        return "/"
    return path[:-1] if path.endswith("/") else path


def _alt_with_slash(path: str) -> str:
    if not path:
        return "/"
    return path if path.endswith("/") else path + "/"
