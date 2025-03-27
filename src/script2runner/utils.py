
def is_using_jupyter() -> bool:
    try:
        tmp = display
        return True
    except:
        return False