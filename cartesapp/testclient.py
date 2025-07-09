import shutil
import os
import glob
import tempfile
import time
from pydantic import BaseModel
from typing import Dict, Any

from cartesi.testclient import MockRollup, TestClient as CartesiTestClient
from cartesi import abi
from cartesi.models import ABIFunctionSelectorHeader

from cartesapp.manager import Manager
from cartesapp.utils import get_modules, hex2bytes, read_config_file, DEFAULT_CONFIGS, deep_merge_dicts
from cartesapp.input import encode_advance_input, encode_inspect_url_input, encode_inspect_jsonrpc_input, encode_query_jsonrpc_input, \
    encode_query_url_input, encode_mutation_input, encode_inspect_json_input, encode_query_json_input
from cartesapp.external_tools import run_cm, run_cmd

import logging

LOGGER = logging.getLogger(__name__)

class InputHelper:
    encode_advance_input = encode_advance_input
    encode_inspect_url_input = encode_inspect_url_input
    encode_inspect_jsonrpc_input = encode_inspect_jsonrpc_input
    encode_inspect_json_input = encode_inspect_json_input
    encode_mutation_input = encode_mutation_input
    encode_query_url_input = encode_query_url_input
    encode_query_jsonrpc_input = encode_query_jsonrpc_input
    encode_query_json_input = encode_query_json_input


class AdvanceInput(BaseModel):
    chain_id:           abi.UInt256
    app_contract:       abi.Address
    msg_sender:         abi.Address
    block_number:       abi.UInt256
    block_timestamp:    abi.UInt256
    prev_randao:        abi.UInt256
    input_index:        abi.UInt256
    payload:            abi.Bytes

class Voucher(BaseModel):
    destination:        abi.Address
    value:              abi.UInt256
    payload:            abi.Bytes

class Notice(BaseModel):
    payload:            abi.Bytes


class CMRollup(MockRollup):
    """Cartesi Machine Rollup Node behavior for using in test suite"""
    tmpdir = tempfile.TemporaryDirectory() # delete=False)

    def __init__(self, **config):
        super().__init__()
        self.testdir = self.tmpdir.name
        self.imagedir = os.path.join(self.testdir,"image")
        self.workdir = os.path.join(self.testdir,"work")

        self.setup_cm(**config)

        self.notice_header = ABIFunctionSelectorHeader(
            function="Notice",
            argument_types=abi.get_abi_types_from_model(Notice)
        ).to_bytes()

        self.voucher_header = ABIFunctionSelectorHeader(
            function="Voucher",
            argument_types=abi.get_abi_types_from_model(Voucher)
        ).to_bytes()

    def setup_cm(self,**config):
        params: Dict[str,Any] = {} | config
        params["store"] = True
        params["base_path"] = self.testdir
        run_cm(**params)

    def send_advance(
            self,
            hex_payload: str,
            msg_sender: str = '0xdeadbeef7dc51b33c9a3e4a21ae053daa1872810',
        ):

        self.block += 1

        advance_input = AdvanceInput(
            chain_id = self.chain_id,
            app_contract = self.app_contract,
            msg_sender = msg_sender,
            block_number = self.block,
            block_timestamp = int(time.time()),
            prev_randao = self.block,
            input_index = self.input,
            payload = hex2bytes(hex_payload)
        )

        abi_types = abi.get_abi_types_from_model(advance_input)
        header = ABIFunctionSelectorHeader(
            function="EvmAdvance",
            argument_types=abi_types
        )
        if os.path.exists(self.workdir): shutil.rmtree(self.workdir)
        base_imagepath = f"{self.workdir}/base_image"
        new_imagepath = f"{self.workdir}/new_image"
        shutil.copytree(self.imagedir,base_imagepath)


        input_filename = f"{self.workdir}/input-%i.bin"
        output_filename = f"{self.workdir}/input-%i-output-%o.bin"
        outputfile_pattern = f"{self.workdir}/input-*-output-*.bin"
        report_filename = f"{self.workdir}/input-%i-report-%o.bin"
        reportfile_pattern = f"{self.workdir}/input-*-report-*.bin"
        outputs_root_hash = f"{self.workdir}/input-%i-output-hashes-root-hash.bin"

        with open(input_filename.replace('%i',f"{self.input}"),'wb') as input_file:
            input_file.write(header.to_bytes()+abi.encode_model(advance_input))

        cm_args = []
        cm_args.append('cartesi-machine')
        cm_args.append(f"--load={base_imagepath}")
        cm_args.append(f"--store={new_imagepath}")
        cm_args.append("--no-rollback")
        cm_args.append("--assert-rolling-template")
        cm_args.append(f"--cmio-advance-state=input:{input_filename},output:{output_filename}," +
            f"report:{report_filename},output_hashes_root_hash:{outputs_root_hash}," +
            f"input_index_begin:{self.input},input_index_end:{self.input+1}")

        result = run_cmd(cm_args,datadirs=[self.testdir],capture_output=True,text=True)
        LOGGER.debug(result.stdout)

        status = True
        if result.returncode != 0:
            msg = f"Error seting cm up: {str(result.stderr)}"
            LOGGER.debug(msg)
            # raise Exception(msg)
            status = False

        for f in glob.iglob(outputfile_pattern):
            if not status: raise Exception("Failed status shouldn't have outputs (only reports)")
            with open(f,'rb') as output_file:
                output_data = output_file.read()
                if output_data[:4] == self.notice_header:
                    notice_model = abi.decode_to_model(data=output_data[4:],model=Notice)
                    data = {
                        'input_index': self.input,
                        'data': {
                            'payload': '0x'+notice_model.payload.hex()
                        }
                    }
                    self.notices.append(data)
                elif output_data[:4] == self.voucher_header:
                    voucher_model = abi.decode_to_model(data=output_data[4:],model=Voucher)
                    data = {
                        'input_index': self.input,
                        'data': {
                            'destination': voucher_model.destination,
                            'value': voucher_model.value,
                            'payload': '0x'+voucher_model.payload.hex(),
                        }
                    }
                    self.vouchers.append(data)

        for f in glob.iglob(reportfile_pattern):
            with open(f,'rb') as output_file:
                data = {
                    'input_index': self.input,
                    'data': {
                        'payload': '0x'+output_file.read().hex(),
                    }
                }
                self.reports.append(data)

        self.status = status
        if status:
            self.input += 1

            if os.path.exists(self.imagedir): shutil.rmtree(self.imagedir)
            shutil.copytree(new_imagepath,self.imagedir)
        if os.path.exists(self.workdir): shutil.rmtree(self.workdir)

    def send_inspect(self, hex_payload: str):
        if os.path.exists(self.workdir): shutil.rmtree(self.workdir)
        base_imagepath = f"{self.workdir}/base_image"
        shutil.copytree(self.imagedir,base_imagepath)

        query_filename = f"{self.workdir}/query.bin"

        report_filename = f"{self.workdir}/query-report-%o.bin"
        reportfile_pattern = f"{self.workdir}/query-report-*.bin"

        with open(query_filename,'wb') as query_file:
            query_file.write(hex2bytes(hex_payload))

        cm_args = []
        cm_args.append('cartesi-machine')
        cm_args.append(f"--load={base_imagepath}")
        cm_args.append("--no-rollback")
        # cm_args.append("--assert-rolling-template")
        cm_args.append(f"--cmio-inspect-state=query:{query_filename},report:{report_filename}")
        # cm_args.append("--skip-root-hash-check")
        # cm_args.append("--skip-root-hash-store")
        cm_args.append("--assert-rolling-template")

        LOGGER.debug(f" cm call: {' '.join(cm_args)}")
        result = run_cmd(cm_args,datadirs=[self.testdir],capture_output=True,text=True)
        LOGGER.debug(result.stdout)

        status = True
        if result.returncode != 0:
            msg = f"Error seting cm up: {str(result.stderr)}"
            LOGGER.debug(msg)
            # raise Exception(msg)
            status = False

        for f in glob.iglob(reportfile_pattern):
            with open(f,'rb') as output_file:
                data = {
                    'data': {
                        'payload': '0x'+output_file.read().hex(),
                    }
                }
                self.reports.append(data)

        self.status = status
        if os.path.exists(self.workdir): shutil.rmtree(self.workdir)

        # def main_loop(self):
        #     """There is no main loop for test rollup."""
        #     return

        def notice(self, payload: str):
            """There is no notice function for cm rollup."""
            return

        def report(self, payload: str):
            """There is no report function for cm rollup."""
            return

        def voucher(self, payload: str):
            """There is no voucher function for cm rollup."""
            return


class TestClient(CartesiTestClient):
    __test__ = False

    def __init__(self,chdir:str | None=None):
        curdir = None
        if chdir is not None:
            curdir = os.getcwd()
            os.chdir(os.path.abspath(chdir))
        if os.getenv('CARTESAPP_TEST_CLIENT') == 'cartesi_machine':
            params: Dict[str,Any] = {} | DEFAULT_CONFIGS
            params = deep_merge_dicts(params, read_config_file(os.getenv('CARTESAPP_CONFIG_FILE')))
            rootfs = os.getenv('TEST_ROOTFS')
            if rootfs is not None:
                params['drives']['root'] = {
                    "builder":"none",
                    "filename":rootfs,
                }
            self.rollup = CMRollup(**params)
        else:
            # Mimics the run command to set up the manager
            m = Manager()
            for mod in get_modules():
                m.add_module(mod)
            m.setup_manager(reset_storage=True)
            super().__init__(m.app)
        self.input_helper = InputHelper
