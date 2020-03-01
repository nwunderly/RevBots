# version 1.0

import ast
import sys
import asyncio
import time
import datetime
import psutil
import random
import yaml
import aiohttp
import signal
import subprocess

import discord
from discord import Webhook, AsyncWebhookAdapter

from asyncio import events
from asyncio import tasks

# custom imports
from authentication import authentication
from authentication import captain_hook
from bots.evalbot import EvalBot


# ----------------------------------------------------------------------------------------------------------------------------------------------------


async def cleanup_python_processes():
    """
    Kills all processes that are running a python program (except this one)
    """
    marvin = await get_process()
    count = 0
    # TODO write this.
    #  maybe put in utility.py? or a wipe_python script?


async def get_process(cmdline=None):
    try:
        if cmdline:
            sudo_cmdline = ['sudo'] + cmdline
            for process in psutil.process_iter():
                if (process_cmdline := process.cmdline()) == cmdline or process_cmdline == sudo_cmdline:
                    return process
        else:
            return psutil.Process()
    except psutil.AccessDenied:
        return None


# ----------------------------------------------------------------------------------------------------------------------------------------------------

class Bot:
    """
    Wraps a bot's subprocess and socket connection.
    get_process() method locates process based on command line
    """
    def __init__(self, name, logger, process=None, cmdline=None):
        self.name = name
        self._started_at = datetime.datetime.now()
        self._reader = None
        self._writer = None
        self._subprocess = process
        self._psutil_process = None
        self._closed = False  # will be set to datetime as of bot being closed
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
        """
        Uses psutil to find Process object pertaining to this bot.
        Returns None if none found.
        """
        self.logger.debug(f"Getting process for {self.name}.")
        if not self.cmdline:
            cmdline = [('python3.8' if sys.platform == 'linux' else 'python'), 'launcher.py', self.name]
        else:
            cmdline = self.cmdline
        self._psutil_process = await get_process(cmdline)
        if p := self._psutil_process:
            self.logger.debug(f"get_process returning {p}.")
            return p
        else:
            self.logger.debug(f"get_process returning None.")
            return None

    async def send(self, data):
        """
        Sends data to the associated bot.
        Data should be a dict.
        """
        self.logger.debug(f"Sending message to {self.name}: {data}")
        if not self._writer:
            self.logger.debug("No writer found.")
            return None
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
        if not self._task.cancelled():
            self._task.cancel()
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self.logger.debug(f"Connection to bot '{self.name}' closed successfully.")

    async def close(self):
        """
        Sends message to bot, requesting that it initiate safe shutdown.
        Uses subprocess first because socket is unable to return whether it was successful.
        (Socket & SIGTERM)
        """
        self.logger.info(f"Sending termination request to {self.name}.")
        self._closed = True
        exit_code = None

        # close socket connection
        # await self.send({'type': 'actionReq', 'details': ['closeBot']})
        await self.disconnect()

        # if subprocess, sends SIGINT (ctrl+c)
        if self._subprocess:
            await self._subprocess.send_signal(signal.SIGINT)
            # await self._subprocess.terminate() would send sigterm.
            self.logger.debug(f"Waiting for {self.name} to terminate. (subprocess)")
            exit_code = await self._subprocess.wait()
            # I wish this method had a timeout

        # no subprocess -> try socket &  wait with psutil (this one allows for timeout)
        if self._psutil_process:
            await self.get_process()
        try:
            self.logger.debug(f"Waiting for {self.name} to terminate. (psutil)")
            exit_code = self._psutil_process.wait(timeout=10)
            self.logger.debug("Process closed successfully.")
        except psutil.NoSuchProcess:
            self.logger.error("Could not find process through psutil. Process was not closed.")
        except psutil.TimeoutExpired:
            self.logger.debug("Error closing bot. Terminating manually.")
            result = await self.kill()
            if result is None:
                self.logger.info(f"Terminating {self.name} failed.")
                return
        self.logger.info(f"{self.name} closed.")
        return exit_code

    async def kill(self):
        """
        Attempts to use subprocess / psutil to force close the bot.
        (SIGKILL)
        """
        self.logger.info(f"Sending kill signal to {self.name}.")
        if self._subprocess:
            await self._subprocess.kill()
            await self._subprocess.wait()
            self.logger.info("Process killed successfully. (subprocess)")
        else:
            self.logger.debug("Subprocess not found. Using psutil.")
            if self._psutil_process:
                self.logger.debug("Cached process found.")
            else:
                self.logger.debug("No cached process. Getting process from psutil.")
                p = await self.get_process()
                if not p:
                    self.logger.debug("No process found. Returning False.")
                    return False
                else:
                    p.terminate()
                    self.logger.info("Process killed successfully. (psutil)")
                    return p.pid


# ----------------------------------------------------------------------------------------------------------------------------------------------------


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
        self._started_at = datetime.datetime.now()
        self._properties = None
        self._port = 8800
        self._bots = dict()
        self._response_queue = dict()
        self._startup_bots = ['bulbe']  # uses this if it can't read from yaml
        self._error_detected = dict()
        self._webhook_session = None    # webhook session
        self._webhook = webhook
        self._today = datetime.datetime.now().day
        self._server = None

    async def try_run(self, coro):
        try:
            return await coro
        except:
            self.logger.error(f"Encountered error in try_run:", exc_info=True)
            return

    async def read_properties(self):
        try:
            with open("configs/marvin.yaml") as f:
                self._properties = yaml.load(f, yaml.Loader)
            return True
        except yaml.YAMLError:
            return False

    async def setup_webhook(self):
        self.logger.debug("setup_webhook called.")
        if 'logging' not in self._properties.keys():
            self.logger.error("Webhook URL not found. Cannot set up webhook.")
            return None
        hook = captain_hook.webhooks[self._properties['logging']]
        session = aiohttp.ClientSession()
        self._webhook_session = session
        self._webhook = Webhook.from_url(hook, adapter=AsyncWebhookAdapter(session))
        return session

    async def on_socket_message(self, bot, data):
        self.logger.debug(f"Message received from {bot.name}: {data}")
        if bot.name != data['from']:
            self.logger.debug(f"Bot name ({data['from']}) did not match socket connection name ({bot.name}). Returning.")
            return
        if data['to'] == 'marvin':
            redirect = {
                "actionReq": self.process_action_req,
                "dataReq": self.process_data_req,
                "response": self.process_response,
                "pong": self.process_response,
                "summon": self.login_as_bot,
                "ping": self.pong,
            }
            await self.try_run(redirect[data['type']](data))
        else:
            if (name := data['to']) in list(self._bots.keys()) and self._bots[name].is_active():
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
            task = asyncio.create_task(self.try_run(self.watch_connection(bot)), name=f'watch_{name}')
            await bot.set_task(task)
        else:
            self.logger.info("Connection was terminated.")

    async def verify_connection(self, reader, writer):
        msg = await reader.readuntil(b'\0')
        self.logger.debug(f"Verification message received: {msg}")
        if (msg := msg.decode('utf-8').replace("\0", "")) in list(self._bots.keys()) and not self._bots[msg].is_bound():
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
        asyncio.create_task(self.try_run(self.on_bot_connect(bot)))
        self.logger.info(f"Watching for messages from {bot.name}.")
        self.logger.debug(f"Waiting for {bot.name} to be bound.")
        try:
            while not bot.is_bound():
                self.logger.debug(f"{bot.name} is not bound yet.")
                await asyncio.sleep(1)
            self.logger.debug(f"{bot.name} is now bound. starting loop.")
            while bot.name in list(self._bots.keys()) and self._bots[bot.name] is not None:
                data = await bot.recv()
                if data:
                    asyncio.create_task(self.try_run(self.on_socket_message(bot, data)))
                else:
                    if bot.name in list(self._bots.keys()):
                        self._bots.pop(bot.name)
                        self.logger.error(f"Connection with {bot.name} has closed unexpectedly.")
                        # await self.hook(f"Connection with {connection.name} has closed unexpectedly.")
                    break
        except asyncio.CancelledError:
            self.logger.debug("Task was cancelled.")
        bot._closed = datetime.datetime.now() if not bot._closed else bot._closed
        self.logger.info(f"No longer watching for messages from {bot.name}.")

    async def process_action_req(self, data):
        """
        Processes messages indicated as requests for Marvin to perform an action.
        """
        details = data['details']
        if isinstance(details, list) and len(details) > 1:
            if details[0] == 'closeServer':
                self.logger.info(f"Closing server; requested by {data['from']}.")
                await self.close()
            elif details[0] == 'closeBot':
                to_close = self._bots[data[1]]
                if to_close in list(self._bots.keys()) and self._bots[to_close].is_active():
                    self.logger.info(f"Closing {to_close}; requested by {data['from']}.")
                    await to_close.close()
            elif details[0] == 'killBot':
                to_kill = self._bots[data[1]]
                if to_kill in list(self._bots.keys()) and self._bots[to_kill].is_active():
                    self.logger.info(f"Terminating {to_kill}; requested by {data['from']}.")
                    await self.kill_process(to_kill)
            elif details[0] == 'startBot':
                to_start = self._bots[data[1]]
                if to_start not in list(self._bots.keys()):
                    self.logger.info(f"Starting {to_start}; requested by {data['from']}.")
                    await self.start_bot(details[1])
        elif isinstance(details, dict):
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

    async def process_data_req(self, data):
        """
        Processes messages indicated as requests for some kind of data.
        Currently only works for bot and system metrics.
        """
        self.logger.debug(f"Processing data request from {data['from']}: {data['details']}")
        details = data['details']
        if isinstance(details, list) and len(details) > 0:
            if details[0] == 'metrics':
                self.logger.info(f"Obtaining metrics data for {details[1]}; requested by {data['from']}")
                result = await self.metrics(details[1])
                response = {'type': 'response', 'details': result}
                await self._bots[data['from']].send(response)
                self.logger.debug("Metrics data sent.")
            else:
                self.logger.debug(f"Data request '{details[0]}")

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

    async def wait_for_response(self, data, timeout=10):
        """
        Waits for a response to outgoing message "data".
        Timeout indicates how long in seconds to wait before timing out.
        Returns None on failure or timeout.
        """
        self.logger.info(f"wait_for response called, data: {data}")
        t = time.monotonic()
        key = (data['to'], data['timestamp'])  # TODO FIX THIS SO PING WORKS WITH METRICS
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

    async def ping(self, bot_name):
        if bot_name in list(self._bots.keys()) and self._bots[bot_name].is_active():
            self.logger.debug(f"Pinging {bot_name}.")
            bot = self._bots[bot_name]
            data = {'type': 'ping'}
            t = time.monotonic()
            sent = await bot.send(data)
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
        if data['from'] in list(self._bots.keys()):
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

    async def webhook_report(self, _type, description, data):
        self.logger.debug(f"Sending webhook report; type '{_type}', data: {data}")
        embed = None
        if _type == 'metrics_warning':
            embed = discord.Embed(title="WARNING", color=discord.Color.red())
            embed.description = description
            keys = list(data.keys())
            _cpu = data['cpu'] if 'cpu' in keys else 0.0
            _ram = data['memory'] if 'memory' in keys else 0.0
            _io = data['io_bytes'] if 'io_bytes' in keys else 0.0
            _s = data['s_ping'] if 's_ping' in keys else 0.0
            _d = data['d_ping'] if 'd_ping' in keys else 0.0
            s = f"CPU:  {_cpu:.4}%\n" \
                f"RAM:  {_ram:.4}%\n" \
                f"IO:   {_io}\n" \
                f"PING: \n" \
                f"--socket:  {_s:.4}\n" \
                f"--discord: {_d:.4}"
            embed.add_field(name=f"Data for {data['who']}:", value=s, inline=False)
        elif _type == 'daily_metrics':
            embed = discord.Embed(title="Daily Summary:", color=discord.Color.blue())
            embed.description = description
            system_data = data['system']
            s = f"CPU: {system_data['cpu']:.4}%\n" \
                f"RAM: {system_data['memory']:.4}%\n"
            embed.add_field(name=f"Data for {system_data['who']}:", value=s, inline=False)
            for bot_data in data['bots']:
                started = bot_data['started_at'] if 'started_at' in bot_data.keys() else None
                stopped = bot_data['stopped_at'] if 'stopped_at' in bot_data.keys() else None
                now = datetime.datetime.now()
                try:
                    duration = (stopped if stopped else now) - started
                except:
                    duration = None
                s = ""
                if duration:
                    s += f"Duration ({'stopped' if stopped else 'running'}): {duration}\n"
                if 'cpu' in bot_data.keys():
                    s += f"CPU: {bot_data['cpu']:.4}%\n"
                if 'memory' in bot_data.keys():
                    s += f"RAM: {bot_data['memory']:.4}%\n"
                if 'io_bytes' in bot_data.keys():
                    s += f"IO: \n" \
                         f"--{bot_data['io_bytes']['read']/1000000:.3} MB read\n" \
                         f"--{bot_data['io_bytes']['write']/1000000:.3} MB written\n"
                if 'd_ping' in bot_data.keys():
                    s += f"Discord ping: {bot_data['d_ping']*1000:.4}ms\n"
                if 's_ping' in bot_data.keys():
                    s += f"Socket ping: {bot_data['s_ping']*1000:.4}ms\n"
                if s == "":
                    s = "No data to report."
                embed.add_field(name=f"Data for {bot_data['who']}:", value=s, inline=False)
        elif _type == 'marvin_start':
            pass
        elif _type == 'socket_warning':
            pass
        else:
            return None
        embed.set_footer(
            text=random.choice(self._properties['short quotes']),
            icon_url='https://cdn.discordapp.com/attachments/540980176062906368/683178179149824031/marvin.jpeg')
        await self._webhook.send(embed=embed)

    async def metrics(self, who):
        """
        Returns psutil analysis of the requested process.
        """
        self.logger.debug(f"Received request to analyze metrics for '{who}'.")
        p = None
        who = who.lower()
        result = dict()
        result['who'] = who
        if who == 'system':
            result['cpu'] = psutil.cpu_percent()
            mem = psutil.virtual_memory()
            # result['memory'] = {'total': mem.total, 'available': mem.available, 'percent': mem.percent}
            result['memory'] = mem.percent
            _io = psutil.net_io_counters()
            result['io_count'] = {'read': _io.packets_recv, 'write': _io.packets_sent}
            result['io_bytes'] = {'read': _io.bytes_recv, 'write': _io.bytes_sent}
            self.logger.debug(f"Sending system metrics: {result}")
            return result
        ping = None
        started_at = None
        stopped_at = None
        if who == 'marvin':
            p = await get_process()
            started_at = self._started_at
            stopped_at = False
        elif who in list(self._bots.keys()):
            bot = self._bots[who]
            p = await self._bots[who].get_process()
            ping = await self.ping(who)
            started_at = bot._started_at
            stopped_at = bot.is_closed()

        # these might be None
        result['started_at'] = started_at
        result['stopped_at'] = stopped_at

        if p is None:
            # no process found
            if ping:
                result['s_ping'], result['d_ping'] = float(ping[0]), float(ping[1])
            self.logger.debug(f"No process found. Sending incomplete metrics for {who}: {result}")
            return result
        try:
            with p.oneshot():
                result['status'] = p.status()
                result['cpu'] = p.cpu_percent() / psutil.cpu_count()
                mem = p.memory_percent()
                result['memory'] = mem
                _io = p.io_counters()
                result['io_count'] = {'read': _io.read_count, 'write': _io.write_count}
                result['io_bytes'] = {'read': _io.read_bytes, 'write': _io.write_bytes}

                result['ping'] = ping

                self.logger.debug(f"Sending metrics for {who}: {result}")
                return result
        except psutil.AccessDenied:
            self.logger.debug(f"Access Denied. Sending incomplete metrics for {who}: {result}")
            if ping:
                result['ping'] = ping
            return result

    async def check_metrics(self):
        self.logger.debug("check_metrics called.")
        system_threshold = {  # threshold for overall CPU/RAM usage
            'cpu':      90,
            'memory':   90,
        }
        bot_threshold = {  # includes check for this
            'cpu':       10,
            'memory':    30,
            'd_ping':   .1,
            's_ping':   .1
        }

        def check(metrics, threshold):
            issues = list()
            for key, value in metrics.items():
                if key not in list(threshold.keys()):
                    pass
                elif threshold[key] is not None and value >= threshold[key]:
                    issues.append(key)
            return issues

        def error_detected(who, set_to=None):
            if set_to is not None:
                self._error_detected[who] = set_to
            elif who not in self._error_detected.keys():
                self._error_detected[who] = False
            return self._error_detected[who]

        # check system
        self.logger.debug("Checking metrics for system.")
        system_data = await self.metrics('system')
        if system_issues := check(system_data, system_threshold):
            self.logger.debug(f"Detected error with system: {system_issues}")
            if not error_detected('system'):
                await self.webhook_report(
                    _type='metrics_warning',
                    description=f"system: {len(system_issues)} values exceeded threshold.",
                    data=system_data)
            error_detected('system', True)
        else:
            error_detected('system', False)

        # check marvin process, and each bot one by one
        for bot in ['marvin'] + list(self._bots.keys()):
            self.logger.debug(f"Checking metrics for {bot}.")
            bot_data = await self.metrics(bot)
            if not bot_data:
                continue
            if bot_issues := check(bot_data, bot_threshold):
                self.logger.debug(f"Detected issues with {bot}: {bot_issues}")
                if not error_detected(bot):
                    await self.webhook_report(
                        _type='metrics_warning',
                        description=f"{bot}: {len(bot_issues)} values exceeded threshold.",
                        data=bot_data)
                    error_detected(bot, True)
            else:
                error_detected(bot, False)

    async def get_daily_metrics(self):
        """
        Returns dict containing data for system, marvin and each bot.
        """
        self.logger.debug("get_daily_metrics called.")

        data = dict()
        self.logger.debug("Checking metrics for system.")
        system_data = await self.metrics('system')
        data['system'] = system_data
        data['bots'] = list()
        for bot in ['marvin'] + list(self._bots.keys()):
            self.logger.debug(f"Checking metrics for {bot}.")
            bot_data = await self.metrics(bot)
            if not bot_data:
                continue
            data['bots'].append(bot_data)
        return data

    async def check_new_day(self):
        self.logger.debug("Checking for new day.")
        if (today := datetime.datetime.now().day) != self._today:
            self.logger.info("New day detected, sending daily stats.")
            self._today = today
            data = await self.get_daily_metrics()
            if data:
                await self.webhook_report(_type='daily_metrics',
                                          description=f"Data for {len(data['bots'])} bots",
                                          data=data)
                self.logger.info("Sent daily stats.")

    async def metrics_loop(self):
        """
        Loop that checks CPU / RAM usage every ten seconds
        Also sends daily system stats once per day.
        """
        self.logger.debug("metrics_loop called.")
        await asyncio.sleep(10)
        while True:
            t = time.monotonic()
            await self.try_run(self.check_metrics())
            self.logger.debug(f"Checked metrics, took {time.monotonic() - t} seconds.")
            await self.try_run(self.check_new_day())
            await asyncio.sleep(30)

    async def kill_process(self, who):
        """
        Attempts to kill a bot through psutil. Bypasses close() method.
        """
        self.logger.info(f"Received request to force kill '{who}'.")
        if who in list(self._bots.keys()):
            self.logger.debug("Killing bot found in cache.")
            pid = await self._bots[who].kill()
            return pid
        else:
            self.logger.debug("Attempting to find and kill process.")
            cmdline = [('python3.8' if sys.platform == 'linux' else 'python'), 'launcher.py', who]
            p = await get_process(cmdline)
            if p == await get_process():
                self.logger.debug("Kill request appears to be for Marvin. Initiating safe shutdown.")
                await self.close()
            elif p:
                p.terminate()
                self.logger.debug(f"Process '{who}' found. Process was terminated.")
                return p.pid
            else:
                self.logger.debug(f"Process '{who}' not found. Nothing was terminated.")
                return None

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
        self.logger.info("close() method called.")
        try:
            for key, bot in self._bots.items():
                self.logger.debug(f"Closing {key}.")
                await bot.close()
            self.logger.debug("Closing server.")
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            self.logger.debug("Closing webhooks.")
            if self._webhook_session:
                await self._webhook_session.close()
        except:
            self.logger.error("An error occurred on shutdown. Exiting.", exc_info=True)
            exit()

    async def start(self):
        self.logger.debug("Initializing server.")
        self._server = await asyncio.start_server(self.on_connection, 'localhost', self._port, loop=self.loop)
        self.logger.info("Starting server.")
        await self.read_properties()
        await self.setup_webhook()
        async with self._server:
            self.logger.debug("Starting bots.")
            to_start = self._properties['startup'] if 'startup' in self._properties.keys() else self._startup_bots
            for bot_name in to_start:
                await self.start_bot(bot_name)
            self.logger.info("Starting metrics loop.")
            asyncio.create_task(self.try_run(self.metrics_loop()))
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
