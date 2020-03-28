from __future__ import print_function
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import ast
import sys

from deprecated.spreadsheet_snippets import SpreadsheetSnippets
from utils.utility import module_logger, stream_logger
from authentication.authentication import linux_username


# If modifying these scopes, delete the file authentication/sheets_token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']


class SheetsException(Exception):
    pass


class SheetsClient:
    def __init__(self, bot_name=None):
        if bot_name:
            self.logger = module_logger(bot_name, 'sheets')
        else:
            self.logger = stream_logger('sheets')
        service = get_service()
        if service:
            self.snippets = SpreadsheetSnippets(service)
        else:
            self.logger.debug("Failed to initialize SheetsClient.")
            raise SheetsException("Failed to initialize SheetsClient.")
        self.logger.debug("SheetsClient initialized and connected.")

    def read(self, file_id, sheet, fields):
        # try:
        _range = f"{sheet}!{fields}"
        spreadsheet = self.snippets.get_values(file_id, _range)
        self.logger.debug(f"successfully read spreadsheet. data: {spreadsheet}")
        if 'values' in spreadsheet.keys():
            rows = spreadsheet['values']
            return rows
        else:
            return []
        # except Exception:
        #     raise SheetsException("Failed to read from file.")

    def read_configs(self, bot):
        _id = '1-zRnmc4f2xa0UpP50mSm1qMtjj56_AP2DvSBu6j4S_o'
        rows = self.read(_id, bot, 'A:C')
        result = {}
        for row in rows:
            result[int(row[0])] = ast.literal_eval(row[2])
        return result

    def read_blacklists(self, bot):
        _id = '1CHrX66kEssvUQqMje_mFqSKZQFGAE58-AGxBHIiMofg'
        rows = self.read(_id, bot, 'A3:D')
        users = []
        guilds = []
        for row in rows:
            users.append(int(row[0]))
            guilds.append(int(row[2]))
        return users, guilds

    def read_guild_data(self, bot):
        _id = '1CHrX66kEssvUQqMje_mFqSKZQFGAE58-AGxBHIiMofg'
        mute_retain_rows = self.read(_id, bot, 'E3:F')
        temp_mute_rows = self.read(_id, bot, 'G3:H')
        temp_ban_rows = self.read(_id, bot, 'I3:J')
        mute_retain = {}
        temp_mute = {}
        temp_ban = {}
        for row in mute_retain_rows:
            mute_retain[str(row[0])] = ast.literal_eval(row[1])
        for row in temp_mute_rows:
            temp_mute[str(row[0])] = ast.literal_eval(row[1])
        for row in temp_ban_rows:
            temp_ban[str(row[0])] = ast.literal_eval(row[1])
        return mute_retain, temp_mute, temp_ban

    def write(self, file_id, sheet, fields, rows):
        # try:
        _range = f"{sheet}!{fields}"
        self.logger.debug(f"writing to {_range}")
        self.snippets.update_values(file_id, _range, "RAW", rows)
        self.logger.debug(f"wrote to {_range}: {rows}")
        # except Exception:
        #     raise SheetsException("Failed to write to file.")

    def write_config(self, bot, data):
        rows = []
        _id = '1-zRnmc4f2xa0UpP50mSm1qMtjj56_AP2DvSBu6j4S_o'
        for key, value in data.items():
            name = value.pop('name')
            rows.append([str(key), name, str(value)])
        self.write(_id, bot, 'A:C', rows)

    def write_blacklists(self, bot, data):
        _id = '1CHrX66kEssvUQqMje_mFqSKZQFGAE58-AGxBHIiMofg'
        users, guilds = data
        u_rows = []
        g_rows = []
        for u_id, u_name in users:
            u_rows.append([str(u_id), u_name])
        for g_id, g_name in guilds:
            g_rows.append([str(g_id), g_name])
        self.write(_id, bot, 'A3:B', u_rows)
        self.write(_id, bot, 'C3:D', g_rows)

    def write_guild_data(self, bot, data):
        _id = '1CHrX66kEssvUQqMje_mFqSKZQFGAE58-AGxBHIiMofg'
        mute_retain, temp_mute, temp_ban = data
        mute_retain_rows = []
        temp_mute_rows = []
        temp_ban_rows = []
        for guild_id, users in mute_retain.items():
            mute_retain_rows.append([str(guild_id), str(users)])
        for guild_id, users in temp_mute.items():
            temp_mute_rows.append([str(guild_id), str(users)])
        for guild_id, users in temp_ban.items():
            temp_ban_rows.append([str(guild_id), str(users)])
        self.write(_id, bot, 'E3:F', mute_retain_rows)
        self.write(_id, bot, 'G3:H', temp_mute_rows)
        self.write(_id, bot, 'I3:J', temp_ban_rows)


def get_service():
    # logger = logging.getLogger('sheets')
    # logger.debug("get_service() called.")
    try:
        creds = get_creds()
        service = build('sheets', 'v4', credentials=creds)
        return service
    except Exception as e:
        print(str(e))
        # logger.error("Error in obtainining credentials and building Sheets service.", exc_info=True)
        return None


def get_creds():
    # logger = logging.getLogger('sheets')
    # logger.debug("get_creds() called.")
    creds = None
    if sys.platform == 'linux':
        path = f'../{linux_username}/authentication/sheets_token.pickle'
    else:
        path = '../RevBots/authentication/sheets_token.pickle'
    if os.path.exists(path):
        with open(path, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(path, 'wb') as token:
            pickle.dump(creds, token)
    return creds


if __name__ == '__main__':
    client = SheetsClient()
    # client.write("A:C", [['mods', 'are', 'gay']])
    # client.write_config(to_write)
    client.read('1CHrX66kEssvUQqMje_mFqSKZQFGAE58-AGxBHIiMofg', 'bulbe', 'A3:D')
    # print(client.read_configs())
    # main()
