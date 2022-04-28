import types
import asyncio
import signal
import addresstool.global_controller as gc
from addresstool.account_ex import my_abi_middleware
from web3 import Web3
from web3.middleware import geth_poa_middleware
import queue
from addresstool.logger import Logger


class GetAddress(object):
    def __init__(self, config):
        self.config = config
        self.logger = Logger()
        self.currentBlock = self.config['start_block']
        self.api = Web3(Web3.HTTPProvider(config['api']))
        self.api.middleware_onion.inject(my_abi_middleware, layer=0)
        self.api.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.blockQueue = queue.Queue()
        self.address = set()
        if self.config['addrOrPublic'] == 1:
            self.data_file = open("./{}_publickey.txt".format(self.config['file']), "a")
        else:
            self.data_file = open("./{}_address.txt".format(self.config['file']), "a")
        self.count = 0

    def _exit(self, signum, frame):
        gc.Stop()
        print(" The tool program is exiting safely...", gc.IsRun())

    def GetTasks(self, loop):
        tasks = [loop.create_task(self.GetBlockInfo()), loop.create_task(self.ProcQueue())]
        return tasks

    def Run(self):
        gc.init()
        gc.Start()
        signal.signal(signal.SIGINT, self._exit)
        signal.signal(signal.SIGTERM, self._exit)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.wait(self.GetTasks(loop)))
        loop.close()

    async def GetBlockInfo(self):
        while gc.IsRun():
            try:
                blockInfo = self.api.eth.get_block(self.currentBlock)
                self.currentBlock -= 1
                # self.blockQueue.put_nowait(blockInfo)
                self.blockQueue.put(blockInfo, block=True)
                print(self.currentBlock, "...")
            except Exception as e:
                self.logger.Error("GetBlockInfo error.", e, screen=True)
            await asyncio.sleep(20)

    async def ProcQueue(self):
        try:
            while gc.IsRun() and self.blockQueue.empty() == False:
                data = self.blockQueue.get_nowait()
                await self.onData(data)
                self.blockQueue.task_done()
            await asyncio.sleep(10)
        except Exception as e:
            self.logger.Error("ProcQueue error [{}]: ".format(self.currentBlock), e, screen=True)

    def _save(self):
        tmp = ""
        while len(self.address) > 0:
            if self.config['addrOrPublic'] == 0:
                tmp += str(self.address.pop()) + "\r\n"
            else:
                (addr, pk) = self.address.pop()
                tmp += str(addr) + ", " + str(pk) + "\r\n"
        self.data_file.write(tmp)

    async def onData(self, data):
        is_to = len(self.config['to']) > 0
        for txid in data.transactions:
            tx = self.api.eth.get_transaction(txid)
            if is_to and tx['to'] not in self.config['to']:
                continue
            code = self.api.eth.get_code(tx['from'])
            balance = self.api.eth.get_balance(tx['from'])
            if code == b'' and balance > self.config['balance']:
                publicKey = ""
                tmpAddr = ""
                if self.config['addrOrPublic'] == 1:
                    raw_tx = self.api.eth.get_raw_transaction(tx.hash)
                    # tmpAddr = self.api.eth.account.recover_transaction(raw_tx)
                    publicKey = self.api.eth.account.recover_transaction_pk(raw_tx)
                    self.address.add((tx['from'], publicKey))
                else:
                    self.address.add(tx['from'])
                self.count = len(self.address)
                if not publicKey:
                    print("from: ", tx['from'], "count: ", self.count)
                else:
                    print("from: ", tx['from'], " publicKey: ", publicKey, "count: ", self.count)
            if gc.IsRun() == False:
                self._save()
                self.data_file.close()
                break
            if self.count >= self.config['max']:
                gc.Stop()
            await asyncio.sleep(2)
