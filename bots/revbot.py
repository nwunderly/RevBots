# version 1.0

import discord
from discord.ext import commands
from discord.client import _cleanup_loop

import ast
import signal
import time
import asyncio
import datetime
import traceback

# custom imports
from utils.utility import setup_logger

# TODO:
#   comment code


class Connection:
    """
    Wrapper for async socket stream.
    """
    def __init__(self, name, reader, writer, logger):
        self.name = name  # to help differentiate when there are multiple
        self._reader = reader  # asyncio streams. handled automatically by send/recv methods
        self._writer = writer
        self.logger = logger

    async def send(self, bot, data):
        # data should be a dict containing "type" and "details" keys.
        # don't put "\0" anywhere in the data
        self.logger.debug(f"Sending message to {bot}: {data}")
        data['to'] = bot
        data['from'] = self.name
        data['timestamp'] = str(datetime.datetime.now())
        encoded = (str(data) + '\0').encode('utf-8')
        self._writer.write(encoded)
        await self._writer.drain()
        return data

    async def recv(self):
        # method to read socket stream.
        # evaluates the string as a python literal then returns the object
        self.logger.debug(f"Receiving message from Marvin.")
        try:
            encoded = await self._reader.readuntil(b'\0')
        except asyncio.IncompleteReadError:
            return
        msg = encoded.decode('utf-8')
        if msg == "" or msg == "\0":
            self.logger.info(f"Connection to Marvin broken. Discarding connection.")
            await self.disconnect()
            return
        self.logger.debug(f"Received message from Marvin: {msg}")
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
        self._writer.close()
        await self._writer.wait_closed()


class RevBot(commands.Bot):
    """
    Base class, takes care of logging, socket, and error handling

    Connects to localhost port 8800 by default, but other ports can be chosen.

    You must pass a name (for socket connection/verification purposes) and a logger into
    the constructor
    """
    def __init__(self, name, command_prefix=None, logger=None, port=8800, use_socket=True, **kwargs):
        self._default_prefix = '__'
        command_prefix = command_prefix if command_prefix else self._default_prefix
        super().__init__(command_prefix, **kwargs)
        self._name = name
        self._use_socket = use_socket
        self._port = port
        self._response_queue = {}
        self.logger = logger if logger else setup_logger(name)
        self.marvin = None
        self.reader, self.writer = None, None
        self.started_at = datetime.datetime.now()
        self.logger.info("RevBot initialization complete.")

    async def on_ready(self):
        """
        Override this to override discord.Client on_ready.
        """
        self.logger.info('Logged in as {0.user}.'.format(self))
        self.logger.info("Connecting to Marvin.")
        # await self.extend_connection()

    async def ping_response(self, channel):
        await channel.send(embed=discord.Embed(title=f"{self._name} ({datetime.datetime.now() - self.started_at})",
                                               description=f"Prefix: `{self.command_prefix}`"))

    async def on_message(self, message):
        if message.bot:
            return
        if (await self.is_owner(message.author)) and message.content == self.user.mention:
            await self.ping_response(message.channel)

    async def on_socket_message(self, data):
        """
        Called when information from the socket is received.
        This function redirects the data to the right function to process it.
        """
        self.logger.debug(f"Listener on_socket_message called.")
        if data['to'] == self._name:
            redirect = {
                "actionReq": self.process_action_req,
                "response": self.process_response,
                "pong": self.process_response,
                "ping": self.pong,
            }
            if data['type'] in redirect.keys():
                # calling the proper processing function
                ref = redirect[data['type']]
                self.logger.debug(f"Redirecting to {ref.__name__}.")
                await ref(data)

    async def extend_connection(self):
        """
        Attempts to establish a connection with the manager's socket server.
        """
        self.reader, self.writer = await asyncio.open_connection('localhost', self._port)
        self.logger.info("Connected to Marvin.")
        self.writer.write((self._name + '\0').encode('utf-8'))
        await self.writer.drain()
        self.logger.debug("Data sent. Attempting to read data.")
        try:
            msg = (await self.reader.readuntil(b'\0')).decode('utf-8').replace("\0", "")
        except asyncio.IncompleteReadError:
            self.logger.error("Failed to read response to verification data.", exc_info=True)
            return
        self.logger.debug(f"Data received: {msg}")
        self.logger.debug(f"Data should be: verified:{self._name}.")
        if msg == f'verified:{self._name}.':
            self.logger.info("Connection verified.")
            self.marvin = Connection(self._name, self.reader, self.writer, self.logger)
            asyncio.create_task(self.watch_connection())
        else:
            self.logger.error("Connection refused.")
            return

    async def watch_connection(self):
        """
        Loop that repeatedly checks the socket for data from the manager process
        """
        self.logger.info(f"Watching for messages from Marvin.")
        try:
            while self.marvin:
                data = await self.marvin.recv()
                if data:
                    await (self.on_socket_message(data))
                else:
                    pass
                    # todo warn that connection was closed. shut down?
                # await asyncio.sleep(1)
        except Exception:
            self.logger.error("Error in watch_connection:", exc_info=True)
            await self.marvin.disconnect()
        self.logger.info(f"Loop ended. No longer watching for messages from Marvin.")

    async def ping(self, bot):
        data = {'type': 'ping'}
        t = time.monotonic()
        sent = await self.marvin.send(bot, data)
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
        self.logger.info(f"Pinged by {data['from']}. Ponging.")
        _pong = {'type': 'response', 'details': {'status': 'success', 'timestamp': data['timestamp'], 'discordPing': str(self.latency)}}
        await self.marvin.send(data['from'], _pong)
        self.logger.info("Pong sent.")

    async def process_action_req(self, data):
        """
        Assembles data['details'] dict into a coroutine and awaits it.
        ex: {'user': id, 'send': 'ok'} -> await bot.get_user(id).send('ok')
        """
        self.logger.debug(f"Processing actionReq data from {data['from']}: {data['details']}")
        details = data['details']
        if details[0] == 'closeBot':
            self.logger.info(f"Closing; requested by server.")
            await self.close()
        _last = self
        for key in (details := data['details']).keys():
            ref = None
            try:
                ref = getattr(_last, key)
            except AttributeError:
                pass
            try:
                ref = getattr(_last, f"get_{key}")
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
            self.logger.info(f"Setting _response_queue[{key}] to {status}.")
            self._response_queue[key] = status, details
        else:
            self.logger.info(f"response data not identified in _response_queue:\n{key}\n{list(self._response_queue.keys())}")

    async def check_for_response(self, key):
        # literally exists to avoid blocking
        # it's useful to have a periodic "filler" async call inside the while loop
        return key in list(self._response_queue.keys())

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
            await asyncio.sleep(.01)
        self.logger.debug(f"Task wait_for_response has timed out. Removing {key} from response queue.")
        self._response_queue.pop(key)

    async def setup(self):
        """
        Called when bot is started, before login.
        Use this for any async tasks to be performed before the bot starts.
        """
        pass

    def run(self, *args, **kwargs):
        """
        Modified version of discord.py's bot.run() method.
        Use in exactly the same way.
        """
        loop = self.loop

        try:
            loop.add_signal_handler(signal.SIGINT, lambda: loop.stop())
            loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
        except NotImplementedError:
            pass

        async def runner():
            try:
                await self.setup()
                if self._use_socket:
                    await self.extend_connection()
                else:
                    self.logger.debug("extend_connection skipped.")
                await self.start(*args, **kwargs)
            finally:
                await self.close()

        def stop_loop_on_completion(f):
            loop.stop()

        future = asyncio.ensure_future(runner(), loop=loop)
        future.add_done_callback(stop_loop_on_completion)
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            self.logger.info('Received signal to terminate bot and event loop.')
        finally:
            future.remove_done_callback(stop_loop_on_completion)
            self.logger.info('Cleaning up tasks.')
            _cleanup_loop(loop)

    async def close(self):
        self.logger.debug("RevBot: Received command to shut down. Beginning safe shutdown sequence.")
        if self.marvin:
            self.logger.info("Disconnecting from socket.")
            await self.marvin.close()
        self.logger.info("Closing connection to discord.")
        await super().close()
