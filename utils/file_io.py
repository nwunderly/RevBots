def read_config(self):  # config.json
    try:
        fp = open("configs/config.json", 'r')
        self._config = json.load(fp)
        fp.close()
        return True
    except IOError as e:  # cant find file / its in use / something else
        self.logger.error(str(e), exc_info=True, stack_info=True)
        return False
    except json.JSONDecodeError as e:  # malformed / corrupted
        self.logger.error(str(e), exc_info=True, stack_info=True)
        return False


def write_config(self):
    try:
        fp = open("configs/config.json", 'w')
        json.dump(self._config, fp)
        fp.close()
        return True
    except Exception as e:
        self.logger.error(str(e), exc_info=True, stack_info=True)
        return False


def read_blacklists(self):
    try:
        fp = open("configs/blacklists.json", 'r')
        x = json.load(fp)
        fp.close()
    except Exception as e:
        self.logger.error(str(e), exc_info=True, stack_info=True)
        return False
    self._user_blacklist = x["user"]
    self._guild_blacklist = x["guild"]
    return True


def write_blacklists(self):
    try:
        fp = open("configs/blacklists.json", 'w')
        x = {"user": self._user_blacklist, "guild": self._guild_blacklist}
        json.dump(x, fp)
        fp.close()
    except Exception as e:
        self.logger.error(str(e), exc_info=True, stack_info=True)
        return False
    self._user_blacklist = x["user"]
    self._guild_blacklist = x["guild"]
    return True
