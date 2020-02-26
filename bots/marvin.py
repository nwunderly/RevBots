# version 1.0

import ast
import sys
import asyncio
import time
import datetime
import psutil

from asyncio import events
from asyncio import tasks

# custom imports
from authentication import authentication
from bots.evalbot import EvalBot

# todo
#   use psutil to try to get process
#   don't say it closed unecpectedly if it was intentional
#   bot status
#   heartbeat
#   diagnose bot being offline


# ----------------------------------------------------------------------------------------------------------------------------------------------------

class Bot:
    """
    Wraps a bot's subprocess and socket connection.
    get_process() method locates process based on command line
    """
    def __init__(self, name, logger, process=None, cmdline=None):
        self.name = name
        self._reader = None
        self._writer = None
        self._subprocess = process
        self._psutil_process = None
        self._closed = False
        self._task = None
        self._task_completed = False
        self.logger = logger
        self.cmdline = cmdline

    def is_bound(self):
        if not self._writer or not self._reader:
            return False
        return True

    def is_closed(self):
        return self._closed

    def is_active(self):
        return self.is_bound() and not self.is_closed()

    async def bind(self, reader, writer):
        if not self.is_bound():
            self._reader = reader
            self._writer = writer
            self.logger.debug(f"{self.name} is now bound")
            return True
        else:
            return False

    async def set_task(self, task):
        if not self._task:
            self._task = task
            return True
        else:
            return False

    async def get_process(self):
        if not self.cmdline:
            cmdline = [('python3.8' if sys.platform == 'linux' else 'python'), 'launcher.py', self.name]
            sudo_cmdline = ['sudo', ('python3.8' if sys.platform == 'linux' else 'python'), 'launcher.py', self.name]
        else:
            cmdline = self.cmdline
            sudo_cmdline = ['sudo'] + self.cmdline
        for process in psutil.process_iter():
            if process.cmdline == cmdline or process.cmdline == sudo_cmdline:
                self._psutil_process = process
                break
        if p := self._psutil_process:
            return p
        else:
            return None

    async def send(self, data):
        """
        Sends data to the associated bot.
        Data should be a dict.
        """
        self.logger.debug(f"Sending message to {self.name}: {data}")
        data['to'] = self.name
        if 'from' not in data.keys():
            data['from'] = 'marvin'
        if 'timestamp' not in data.keys():
            data['timestamp'] = str(datetime.datetime.now())
        encoded = (str(data) + '\0').encode('utf-8')
        self._writer.write(encoded)
        await self._writer.drain()
        return data

    async def recv(self):
        """
        Attempts to read a message from bot.
        Waits until it receives a message, returns None if connection is lost.
        """
        self.logger.debug(f"Receiving message from bot '{self.name}'")
        try:
            encoded = await self._reader.readuntil(b'\0')
        except asyncio.IncompleteReadError:
            return
        msg = encoded.decode('utf-8')
        if msg == "" or msg == "\0":
            self.logger.info(f"Connection to {self.name} broken. Discarding connection.")
            await self.disconnect()
            return
        self.logger.debug(f"Received message from {self.name}: {msg}")
        try:
            data = ast.literal_eval(msg.replace("\0", ""))  # should be dict
        except SyntaxError:
            return
        if type(data) is not dict:
            return
        return data

    async def disconnect(self):
        """
        Closes connection with the bot.
        """
        self.logger.debug(f"Closing connection with '{self.name}'.")
        self._writer.close()
        await self._writer.wait_closed()
        self.logger.debug(f"Connection to bot '{self.name}' closed successfully.")

    async def close(self):
        """
        Sends message to bot, requesting that it initiate safe shutdown.
        """
        self.logger.debug(f"Sending termination request to {self.name}.")
        self._closed = True
        await self.send({'type': 'actionReq', 'details': ['closeBot']})
        await self.disconnect()
        self.logger.debug(f"{self.name} closed.")


class Marvin:
    """
    Here I am with a brain the size of a planet and they ask me to turn Juan on and off.

    Bot manager class.
    Handles starting bot, obtaining connection, and managing the connection.
    Redirects inter-bot communication to the correct source.
    """
    def __init__(self, logger, webhook=None):
        self.logger = logger
        self.loop = events.new_event_loop()
        self._port = 8800
        self._bots = {}
        # self._connections = {}
        # self._subprocesses = {}
        self._response_queue = {}
        self._startup_bots = ['bulbe']
        self._webhook_session = None    # webhook session
        self._webhook = webhook
        self._server = None

    async def on_socket_message(self, bot, data):
        self.logger.debug(f"Message received from {bot.name}: {data}")
        if bot.name != data['from']:
            self.logger.debug(f"Bot name ({data['from']}) did not match socket connection name ({bot.name}). Returning.")
            return
        if data['to'] == 'marvin':
            redirect = {
                "actionReq": self.process_action_req,
                "response": self.process_response,
                "pong": self.process_response,
                "summon": self.login_as_bot,
                "ping": self.pong,
            }
            await redirect[data['type']](data)
        else:
            if (name := data['to']) in self._bots.keys() and self._bots[name].is_active():
                await self._bots[data['to']].send(data)  # forwards to other bot
            else:
                self.logger.debug(f"Socket message ignored: {data}")

    async def on_bot_connect(self, connection):  # after verifying connection
        self.logger.debug(f"on_bot_connect called. [{connection.name}]")

    async def on_connection(self, reader, writer):
        self.logger.info(f"Received incoming connection. Attempting to verify.")
        name = await self.verify_connection(reader, writer)
        if name:
            self.logger.debug(f"Setting up connection to {name}.")
            bot = self._bots[name]
            if not await bot.bind(reader, writer):
                self.logger.debug("Failed to bind. Closing connection.")
                writer.close()
                await writer.wait_closed()
                return
            task = asyncio.create_task(self.watch_connection(bot), name=f'watch_{name}')
            await bot.set_task(task)
        else:
            self.logger.info("Connection was terminated.")

    async def verify_connection(self, reader, writer):
        msg = await reader.readuntil(b'\0')
        self.logger.debug(f"Verification message received: {msg}")
        if (msg := msg.decode('utf-8').replace("\0", "")) in self._bots.keys() and not self._bots[msg].is_bound():
            self.logger.info(f"Verified as {msg}.")
            writer.write(f"verified:{msg}.\0".encode('utf-8'))
            await writer.drain()
            return msg
        else:
            self.logger.info(f"Could not verify. Closing connection. ({msg})")
            writer.close()
            await writer.wait_closed()
            return False

    async def watch_connection(self, bot):
        asyncio.create_task(self.on_bot_connect(bot))
        self.logger.info(f"Watching for messages from {bot.name}.")
        self.logger.debug(f"Waiting for {bot.name} to be bound.")
        while not bot.is_bound():
            self.logger.debug(f"{bot.name} is not bound yet.")
            await asyncio.sleep(1)
        self.logger.debug(f"{bot.name} is now bound. starting loop.")
        while bot.name in self._bots.keys() and self._bots[bot.name] is not None:
            data = await bot.recv()
            if data:
                asyncio.create_task(self.on_socket_message(bot, data))
            else:
                if bot.name in self._bots.keys():
                    self._bots.pop(bot.name)
                    self.logger.error(f"Connection with {bot.name} has closed unexpectedly.")
                    # await self.hook(f"Connection with {connection.name} has closed unexpectedly.")
                break
        self.logger.info(f"No longer watching for messages from {bot.name}.")

    async def process_action_req(self, data):
        details = data['details']
        if details[0] == 'closeServer':
            self.logger.info(f"Closing server; requested by {data['from']}.")
            await self.close()
        elif details[0] == 'closeBot':
            to_close = self._bots[data[1]]
            if to_close in self._bots.keys() and self._bots[to_close].is_active():
                self.logger.info(f"Closing {to_close}; requested by {data['from']}.")
                await to_close.close()
        elif details[0] == 'killBot':
            to_kill = self._bots[data[1]]
            if to_kill in self._bots.keys() and self._bots[to_kill].is_active():
                self.logger.info(f"Terminating {to_kill}; requested by {data['from']}.")
                await self.kill_process(to_kill)
        elif details[0] == 'startBot':
            to_start = self._bots[data[1]]
            if to_start not in self._bots.keys():
                self.logger.info(f"Starting {to_start}; requested by {data['from']}.")
                await self.start_bot(details[1]),
        elif details[0] == 'metrics':
            await self.metrics(details[1])
        else:
            _last = self
            for key in (details := data['details']).keys():
                ref = None
                try:
                    ref = getattr(_last, key)
                except AttributeError:
                    pass
                if details[key] is None:
                    _last = ref
                    continue
                if ref:
                    if type((kwargs := details[key])) == dict:
                        _last = ref(**kwargs)
                    elif type((args := details[key])) in [list, tuple]:
                        _last = ref(*args)
                    elif type((arg := details[key])) in [str, int]:
                        _last = ref(arg)
            await _last

    async def process_response(self, data):
        """
        Processes messages indicated as responses to a request from this bot.
        """
        self.logger.debug(f"Processing response data from {data['from']}: {data['details']}")
        details = data['details']  # {'status': True, 'timestamp': datetime}
        status = {'success': True, 'failed': False}[details.pop('status')]
        request_timestamp = details.pop('timestamp')
        if (key := (data['from'], request_timestamp)) in list(self._response_queue.keys()):
            self.logger.debug(f"Setting _response_queue[{key}] to {status}.")
            self._response_queue[key] = status, details
        else:
            self.logger.debug(f"Response data not identified in _response_queue: {key} - {self._response_queue.keys()}")

    async def check_for_response(self, key):
        # literally exists to avoid blocking
        # it's useful to have a periodic "filler" async call inside the while loop
        return key in list(self._response_queue.keys())

    # async def wait_for_response(self, data, timeout=10):
    #     """
    #     Waits for a response to outgoing message "data".
    #     Timeout indicates how long in seconds to wait before timing out.
    #     Returns None on failure or timeout.
    #     """
    #     self.logger.debug(f"wait_for response called, data: {data}")
    #     t = time.monotonic()
    #     key = (data['to'], data['timestamp'])
    #     self._response_queue[key] = None
    #     # response_queue[key] should be True, False, or None depending on the status of the action
    #     self.logger.debug(f"Waiting for response for {key}.\n_response_queue: {self._response_queue.keys()}")
    #     while time.monotonic() - t < timeout:
    #         if await self.check_for_response(key):
    #             if (status := self._response_queue[key]) in [True, False]:
    #                 # will be True if success, False if failed.
    #                 self.logger.debug(f"Response has been detected for {key}. Returning.")
    #                 self._response_queue.pop(key)
    #                 return status
    #             elif status is not None:
    #                 # None means it's still waiting.
    #                 # function will return if something else is detected
    #                 return
    #         else:
    #             self.logger.debug(f"Key {key} is not in response queue. Exiting wait_for_response.")
    #             return
    #         await asyncio.sleep(.01)
    #     self.logger.info(f"Task wait_for_response has timed out. Removing {key} from response queue.")
    #     self._response_queue.pop(key)

    async def wait_for_response(self, data, timeout=10):
        """
        Waits for a response to outgoing message "data".
        Timeout indicates how long in seconds to wait before timing out.
        Returns None on failure or timeout.
        """
        self.logger.info(f"wait_for response called, data: {data}")
        t = time.monotonic()
        key = (data['to'], data['timestamp'])
        self._response_queue[key] = None
        # response_queue[key] should be True, False, or None depending on the status of the action
        self.logger.debug(f"Waiting for response for {key}.\n_response_queue: {self._response_queue.keys()}")
        while time.monotonic() - t < timeout:
            if await self.check_for_response(key):
                status = self._response_queue[key]
                if status is None:
                    # None means it's still waiting on a response
                    pass
                elif type(status) is tuple and len(status) == 2:
                    # first element will be True if success, False if failed.
                    # second element will be dict containing extra into transmitted along with the response
                    self.logger.debug(f"Response has been detected for {key}. Returning.")
                    self._response_queue.pop(key)
                    return status
                elif status in [True, False]:
                    # will be True if success, False if failed.
                    self.logger.debug(f"Response has been detected for {key}. Returning.")
                    self._response_queue.pop(key)
                    return status, None
                else:
                    # function will return if something unexpected is detected
                    self.logger.debug(f"Invalid response detected for {key}. Continuing")
                    continue
            else:
                self.logger.debug(f"Key {key} is not in response queue. Exiting wait_for_response.\n"
                                  f"_response_queue: {self._response_queue.keys}")
                return
            # await asyncio.sleep(.01)
        self.logger.debug(f"Task wait_for_response has timed out. Removing {key} from response queue.")
        self._response_queue.pop(key)

    async def ping(self, bot_name):
        if bot_name in self._bots.keys() and self._bots[bot_name].is_active():
            self.logger.debug(f"Pinging {bot_name}.")
            bot = self._bots[bot_name]
            data = {'type': 'ping'}
            t = time.monotonic()
            sent = await bot.send(bot, data)
            result = await self.wait_for_response(sent)
            if result is None or type(result) is not tuple:
                return
            else:
                if len(result) != 2:
                    return
                details = result[1]
                delta = time.monotonic() - t
                try:
                    p = details.pop('discordPing')
                except KeyError:
                    p = None
                return delta, p

    async def pong(self, data):
        self.logger.debug(f"Pinged by {data['from']}. Ponging.")
        if data['from'] in self._bots.keys():
            _pong = {'type': 'pong', 'details': {'status': 'success', 'timestamp': data['timestamp'], 'discordPing': None}}
            await self._bots[data['from']].send(_pong)
            self.logger.debug(f"Pong sent. ({data['from']})")
        else:
            self.logger.debug(f"Pong failed because the source could not be found. ({data['from']})")

    async def start_bot(self, name):
        self.logger.info(f"Starting {name}.")
        # if sys.platform == 'linux':
        #     p = await asyncio.create_subprocess_exec('python3', 'launcher.py', name,
        #                                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,)
        # else:
        #     p = await asyncio.create_subprocess_exec('python', 'launcher.py', name,
        #                                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        #                                              creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        # self._bots[name] = Bot(name, self.logger, p)
        self._bots[name] = Bot(name, self.logger)

    async def login_as_bot(self, data):
        bot = EvalBot(command_prefix='__')
        bot.marvin = self

        @bot.event
        async def on_ready():
            self.logger.info(f"Logged in as {bot.user}.")
            channel = bot.get_channel(data['details'])
            await channel.send(f"Successfully logged in. Possession protocol complete. Prefix: `__`")

        await bot.start(authentication.tokens[data['from']])

    async def close(self):
        self.logger.info("close() method called")
        for key, bot in self._bots.items():
            self.logger.debug(f"Closing {key}.")
            await bot.close()
        self.logger.debug("Closing server.")
        self._server.close()
        await self._server.wait_closed()
        self._server = None
        self.logger.debug("Closing webhooks.")
        if self._webhook_session:
            self._webhook_session.close()

    async def start(self):
        self.logger.debug("Initializing server.")
        self._server = await asyncio.start_server(self.on_connection, 'localhost', self._port, loop=self.loop)
        self.logger.info("Starting server.")
        async with self._server:
            self.logger.debug("Starting bots.")
            for bot_name in self._startup_bots:
                await self.start_bot(bot_name)
            self.logger.debug("Serving forever.")
            await self._server.serve_forever()

    def run(self, debug=False):

        if events._get_running_loop() is not None:
            raise RuntimeError("There is already a running event loop")

        async def runner():
            try:
                await self.start()
            finally:
                await self.close()

        loop = self.loop
        try:
            events.set_event_loop(loop)
            loop.set_debug(debug)
            loop.run_until_complete(runner())
        except KeyboardInterrupt:
            self.logger.info("Received signal to terminate tasks and event loop.")
        finally:
            try:
                self.logger.debug("Cleaning up tasks.")
                _cancel_all_tasks(loop)
                loop.run_until_complete(loop.shutdown_asyncgens())
                # loop.run_until_complete(loop.shutdown_default_executor())
            finally:
                events.set_event_loop(None)
                self.logger.info("Closing event loop.")
                # loop.close()


def _cancel_all_tasks(loop):
    to_cancel = tasks.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(
        tasks.gather(*to_cancel, loop=loop, return_exceptions=True))

    for task in to_cancel:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler({
                'message': 'unhandled exception during asyncio.run() shutdown',
                'exception': task.exception(),
                'task': task,
            })
