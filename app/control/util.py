
def ok(config, term: str):
    return term is not None and term not in config.TERMS_FOR_MISSING