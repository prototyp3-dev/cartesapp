import subprocess
import shutil
import os
import glob
import tempfile
import time
from pydantic import BaseModel

from cartesi.testclient import MockRollup, TestClient as CartesiTestClient
from cartesi import abi
from cartesi.models import ABIFunctionSelectorHeader

from cartesapp.manager import Manager
from cartesapp.utils import get_modules, hex2bytes
from cartesapp.input import encode_advance_input, encode_inspect_input, encode_query_input, encode_mutation_input
from cartesapp.external_tools import run_cmd

import logging

LOGGER = logging.getLogger(__name__)

class InputHelper:
    encode_advance_input = encode_advance_input
    encode_inspect_input = encode_inspect_input
    encode_mutation_input = encode_mutation_input
    encode_query_input = encode_query_input


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

    def __init__(self, rootfs: str = '.cartesi/root.ext2', rootdir: str = '.'):
        super().__init__()
        self.testdir = self.tmpdir.name
        self.imagedir = f"{self.testdir}/image"
        self.workdir = f"{self.testdir}/work"

        self.cm_rootfs = f"{self.testdir}/root.ext2"
        if not os.path.isabs(rootfs):
            rootfs = os.path.abspath(os.path.join(rootdir,rootfs))
        shutil.copyfile(rootfs, self.cm_rootfs)

        self.setup_cm()

        from cartesi.models import ABIFunctionSelectorHeader
        self.notice_header = ABIFunctionSelectorHeader(
            function="Notice",
            argument_types=abi.get_abi_types_from_model(Notice)
        ).to_bytes()

        self.voucher_header = ABIFunctionSelectorHeader(
            function="Voucher",
            argument_types=abi.get_abi_types_from_model(Voucher)
        ).to_bytes()

    def setup_cm(self):

        dapp_flash = f"{self.testdir}/dapp.sqfs"
        dapp_flash_args = ["mksquashfs",os.path.abspath('.'),dapp_flash,
            "-noI","-noD","-noF","-noX","-wildcards","-e","... .*","-e","... __pycache__"]
        result1 = run_cmd(dapp_flash_args,datadir=self.testdir,capture_output=True,text=True)
        LOGGER.debug(result1.stdout)
        if result1.returncode != 0:
            msg = f"Error seting cm up (creating dapp flash drive): {str(result1.stderr)}"
            LOGGER.error(msg)
            raise Exception(msg)

        # args3.extend(["xgenext2fs","--faketime","--size-in-blocks", str(flashdrive_bsize),
        #           "--block-size",str(config['blocksize']),f"/mnt/{config['flashdrivename']}.ext2"])
        data_flash = f"{self.testdir}/data.ext2"
        data_flash_args = ["xgenext2fs","-fzB","4096","-i","4096","-r","+16384",data_flash]
        result2 = run_cmd(data_flash_args,datadir=self.testdir,capture_output=True,text=True)
        LOGGER.debug(result2.stdout)
        if result2.returncode != 0:
            msg = f"Error seting cm up (creating data flash drive): {str(result2.stderr)}"
            LOGGER.error(msg)
            raise Exception(msg)

        cm_args = []
        cm_args.append('cartesi-machine')
        # cm_args.append("--assert-rolling-template")
        cm_args.append(f"--flash-drive=label:root,filename:{self.cm_rootfs}")
        cm_args.append(f"--flash-drive=label:dapp,filename:{dapp_flash}")
        cm_args.append(f"--flash-drive=label:data,filename:{data_flash}")
        cm_args.append("--workdir=\"/mnt/dapp\"")
        cm_args.append(f"--store={self.imagedir}")
        # cm_args.append("--skip-root-hash-check")
        # cm_args.append("--skip-root-hash-store")
        cm_args.append("--assert-rolling-template")
        cm_args.extend(["--","rollup-init","cartesapp","run"])
        LOGGER.debug(f" cm call: {os.getcwd()} {' '.join(cm_args)}")
        result3 = run_cmd(cm_args,datadir=self.testdir,capture_output=True,text=True)
        LOGGER.debug(result3.stdout)

        if result3.returncode != 0:
            msg = f"Error seting cm up: {str(result3.stderr)}"
            LOGGER.error(msg)
            raise Exception(msg)

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
            block_timestamp = timestamp,
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

        result = run_cmd(cm_args,datadir=self.testdir,capture_output=True,text=True)
        LOGGER.debug(result.stdout)

        status = True
        if result.returncode != 0:
            msg = f"Error seting cm up: {str(result.stderr)}"
            LOGGER.debug(msg)
            # raise Exception(msg)
            status = False

        for f in glob.iglob(outputfile_pattern):
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
        result = run_cmd(cm_args,datadir=self.testdir,capture_output=True,text=True)
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
        if os.getenv('TEST_CLIENT') == 'cartesi_machine':
            # Run tests with current code inside cartesi machine
            params = {'rootdir':curdir}
            if os.getenv('TEST_ROOTFS') is not None:
                params['rootfs'] = os.getenv('TEST_ROOTFS')
            self.rollup = CMRollup(**params)
        else:
            # Mimics the run command to set up the manager
            m = Manager()
            for mod in get_modules():
                m.add_module(mod)
            m.setup_manager(reset_storage=True)
            super().__init__(m.app)
        self.input_helper = InputHelper
