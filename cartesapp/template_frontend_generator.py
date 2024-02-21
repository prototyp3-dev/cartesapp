from pydantic2ts.cli.script import generate_json_schema
import os
import json
import subprocess
import tempfile
from jinja2 import Template
from packaging.version import Version
import re

from .output import MAX_SPLITTABLE_OUTPUT_SIZE

FRONTEND_PATH = 'frontend'
DEFAULT_LIB_PATH = 'src'
PACKAGES_JSON_FILENAME = "package.json"
TSCONFIG_JSON_FILENAME = "tsconfig.json"

def convert_camel_case(s, title_first = False):
    snaked = re.sub(r'(?<!^)(?=[A-Z])', '_', s).lower()
    splitted = snaked.split('_')
    return (splitted[0] if not title_first else splitted[0].title()) + ''.join(i.title() for i in splitted[1:])

def render_templates(settings,mutations_info,queries_info,notices_info,reports_info,vouchers_info,modules_to_add,libs_path=DEFAULT_LIB_PATH):

    add_indexer_query = False
    add_dapp_relay = False
    add_wallet = False
    for module_name in settings:
        if not add_indexer_query and hasattr(settings[module_name],'INDEX_OUTPUTS') and getattr(settings[module_name],'INDEX_OUTPUTS'): 
            add_indexer_query = True
        if not add_dapp_relay and hasattr(settings[module_name],'ENABLE_DAPP_RELAY') and getattr(settings[module_name],'ENABLE_DAPP_RELAY'):
            add_dapp_relay = True
        if not add_wallet and hasattr(settings[module_name],'ENABLE_WALLET') and getattr(settings[module_name],'ENABLE_WALLET'):
            add_wallet = True
        if add_indexer_query and add_dapp_relay and add_wallet:
            break
            

    modules = modules_to_add.copy()

    helper_template_output = Template(cartesapp_utils_template).render({
        "MAX_SPLITTABLE_OUTPUT_SIZE":MAX_SPLITTABLE_OUTPUT_SIZE
    })

    cartesapppath = f"{FRONTEND_PATH}/{libs_path}/cartesapp"
    if not os.path.exists(cartesapppath):
        os.makedirs(cartesapppath)

    with open(f"{cartesapppath}/utils.ts", "w") as f:
        f.write(helper_template_output)

    create_lib_file = False
    indexer_query_info = None
    indexer_output_info = None
    if add_indexer_query:
        indexer_query_info = queries_info["indexer.indexer_query"]
        indexer_output_info = reports_info["indexer.IndexerOutput"]
        modules.append('indexer')
        create_lib_file = True

    if add_dapp_relay:
        modules.append('relay')

    if add_wallet:
        modules.append('wallet')

    if create_lib_file:
        helper_lib_template_output = Template(cartesapp_lib_template).render({
            "convert_camel_case":convert_camel_case,
            "add_indexer_query": add_indexer_query,
            "add_dapp_relay": add_dapp_relay,
            "indexer_query_info": indexer_query_info,
            "indexer_output_info": indexer_output_info,
            "MAX_SPLITTABLE_OUTPUT_SIZE":MAX_SPLITTABLE_OUTPUT_SIZE
        })

        with open(f"{cartesapppath}/lib.ts", "w") as f:
            f.write(helper_lib_template_output)


        
    modules_processed = []
    while len(modules) > 0:
        module_name = modules.pop()
        modules_processed.append(module_name)

        module_notices_info = [i for i in notices_info.values() if i['module'] == module_name]
        module_reports_info = [i for i in reports_info.values() if i['module'] == module_name]
        module_vouchers_info = [i for i in vouchers_info.values() if i['module'] == module_name]
        module_mutations_info = [i for i in mutations_info.values() if i['module'] == module_name and i['configs'].get('specialized_template') is None]
        module_queries_info = [i for i in queries_info.values() if i['module'] == module_name]

        mutations_payload_info  = [dict(p) for p in set([(("abi_types",tuple(i["abi_types"])),("model",i["model"])) for i in module_mutations_info])]
        for i in mutations_payload_info: i["abi_types"] = list(i["abi_types"])
        queries_payload_info    = [dict(p) for p in set([(("abi_types",tuple(i["abi_types"])),("model",i["model"])) for i in module_queries_info])]
        for i in queries_payload_info: i["abi_types"] = list(i["abi_types"])

        models = []
        models.extend(map(lambda i:i['model'],module_notices_info))
        models.extend(map(lambda i:i['model'],module_reports_info))
        models.extend(map(lambda i:i['model'],module_vouchers_info))
        models.extend(map(lambda i:i['model'],module_mutations_info))
        models.extend(map(lambda i:i['model'],module_queries_info))
        models = list(set(models))

        frontend_lib_path = f"{FRONTEND_PATH}/{libs_path}/{module_name}"

        filepath = f"{frontend_lib_path}/lib.ts"

        specialized_templates = ''
        for i in mutations_info.values():
            if i['module'] == module_name and i['configs'].get('specialized_template'):
                specialized_templates += i['configs'].get('specialized_template')
        
        if len(models) > 0 or len(specialized_templates) > 0:
            if not os.path.exists(frontend_lib_path):
                os.makedirs(frontend_lib_path)

            with open(filepath, "w") as f:
                f.write(lib_template_std_imports)
                
        if len(models) > 0:

            schema = generate_json_schema(models)

            output_filepath = f"{frontend_lib_path}/ifaces.d.ts"

            schema_temp = tempfile.NamedTemporaryFile()
            schema_file = schema_temp.file
            schema_file_path = schema_temp.name

            with open(schema_file_path, "w") as f:
                f.write(schema)

            args = ["npx","json2ts"]
            args.extend(["-i",schema_file_path])
            args.extend(["-o",output_filepath])

            result = subprocess.run(args, capture_output=True, text=True)
            if result.returncode > 0:
                raise Exception("Error generating typescript interfaces")

            schema_temp.close()

        if len(specialized_templates) > 0:
            with open(filepath, "a") as f:
                f.write(specialized_templates)

        if len(models) > 0:
            has_indexer_query = False
            module_setting = settings.get(module_name)
            if module_setting is not None and hasattr(module_setting,'INDEX_OUTPUTS'):
                has_indexer_query = getattr(module_setting,'INDEX_OUTPUTS')

            # lib_template_file = open('templates/lib.j2','r')
            # lib_template = lib_template_file.read()
            # lib_template_file.close()
            
            lib_template_output = Template(lib_template).render({
                "MAX_SPLITTABLE_OUTPUT_SIZE":MAX_SPLITTABLE_OUTPUT_SIZE,
                "mutations_info":module_mutations_info,
                "queries_info":module_queries_info,
                "mutations_payload_info":mutations_payload_info,
                "queries_payload_info":queries_payload_info,
                "notices_info":module_notices_info,
                "reports_info":module_reports_info,
                "vouchers_info":module_vouchers_info,
                "has_indexer_query": has_indexer_query,
                "list":list,
                "convert_camel_case":convert_camel_case
            })

            with open(filepath, "a") as f:
                f.write(lib_template_output)

def get_newer_version(pkg_name,req_version,orig_version):
    if orig_version is None: return req_version
    ov = Version(orig_version.split('~')[-1].split('^')[-1])
    rv = Version(req_version.split('~')[-1].split('^')[-1])
    force_original = False
    if req_version.startswith('~') or orig_version.startswith('~'):
        if ov.major != rv.major or ov.minor != rv.minor:
            force_original = True
    if req_version.startswith('^'):
        if not orig_version.startswith('^') and ov < rv:
            force_original = True
    if orig_version.startswith('^'):
        if not req_version.startswith('^') and rv < ov:
            force_original = True
    if force_original:
        print(f"WARN: Required package {pkg_name} version is {req_version} but original is {orig_version}: keeping original (fix this manually)")
        return orig_version
    newer = orig_version
    if rv > ov: newer = req_version
    return newer


def create_frontend_structure(libs_path=DEFAULT_LIB_PATH):
    # packages json
    pkg_path = f"{FRONTEND_PATH}/{PACKAGES_JSON_FILENAME}"
    original_pkg = {}
    # merge confs (warn and keep original)
    if os.path.exists(pkg_path) and os.path.isfile(pkg_path):
        with open(pkg_path, "r") as f:
            original_json_str = f.read()
            original_pkg = json.loads(original_json_str)
    for section in packages_json:
        if original_pkg.get(section) is None: original_pkg[section] = {}
        for key in packages_json[section]:
            if "dependencies" in section.lower():
                original_pkg[section][key] = get_newer_version(key,packages_json[section][key],original_pkg[section].get(key))
            else:
                if original_pkg[section].get(key) is not None and original_pkg[section][key] != packages_json[section][key]:
                    print(f"WARN: Required package {key} section is '{packages_json[section][key]}' but original is '{original_pkg[section][key]}': keeping original (fix this manually)")
                original_pkg[section][key] = original_pkg[section].get(key) or packages_json[section][key]

    # tsconfig json
    tscfg_path = f"{FRONTEND_PATH}/{TSCONFIG_JSON_FILENAME}"
    original_tscfg = {}
    # merge confs (warn and keep original)
    if os.path.exists(tscfg_path) and os.path.isfile(tscfg_path):
        with open(tscfg_path, "r") as f:
            original_json_str = f.read()
            original_tscfg = json.loads(original_json_str)
    # tsconfig_json['include'] = [libs_path]
    for section in tsconfig_json:
        if type(tsconfig_json[section]) == type({}):
            if original_tscfg.get(section) is None: original_tscfg[section] = {}
            for key in tsconfig_json[section]:
                if original_tscfg[section].get(key) is not None and original_tscfg[section][key] != tsconfig_json[section][key]:
                    print(f"WARN: Required tsconfig {section} section is '{json.dumps(tsconfig_json[section][key])}' but original is '{json.dumps(original_tscfg[section][key])}': keeping original (fix this manually)")
                original_tscfg[section][key] = original_tscfg[section].get(key) or tsconfig_json[section][key]
        elif type(tsconfig_json[section]) == type([]):
            if original_tscfg.get(section) is None: original_tscfg[section] = []
            for val in tsconfig_json[section]:
                if val not in original_tscfg[section]:
                    original_tscfg[section].append(val)



    if not os.path.exists(FRONTEND_PATH):
        os.makedirs(FRONTEND_PATH)

    with open(pkg_path, "w") as f:
        json_str = json.dumps(original_pkg, indent=2)
        f.write(json_str)

    with open(tscfg_path, "w") as f:
        json_str = json.dumps(original_tscfg, indent=2)
        f.write(json_str)

packages_json = {
    "scripts": {
        # "dry-run": "ts-node src/dry-run.ts",
        # "prepare": "ts-patch install"
    },
    "dependencies": {
        "ajv": "^8.12.0",
        "ajv-formats": "^2.1.1",
        "ethers": "^5.7.2"
    },
    "devDependencies": {
        "@types/node": "^20",
        "typescript": "^5",
        # "ts-patch": "^3.1.2",
        # "ts-transformer-keys": "^0.4.4",
        # "ts-node": "^10.9.2"
    }
}

tsconfig_json = {
    # "ts-node": {
    #   // This can be omitted when using ts-patch
    #   "compiler": "ts-patch/compiler"
    # },
    "compilerOptions": {
        # "strict": True,
        # "noEmitOnError": True,
        # # "suppressImplicitAnyIndexErrors": true,
        "target": "es2015",
        # "plugins": [
        #     { "transform": "ts-transformer-keys/transformer" }
        # ]
    }
}

cartesapp_utils_template = '''/* eslint-disable */
/**
 * This file was automatically generated by cartesapp.template_generator.
 * DO NOT MODIFY IT BY HAND. Instead, run the generator,
 */
import { Signer, ethers, ContractReceipt } from "ethers";
import Ajv, { ValidateFunction } from "ajv"
import addFormats from "ajv-formats"

import { 
    advanceInput, inspect, 
    AdvanceOutput, InspectOptions, AdvanceInputOptions,
    Report as CartesiReport, Notice as CartesiNotice, Voucher as CartesiVoucher, 
    Maybe, Proof, validateNoticeFromParams, wasVoucherExecutedFromParams, executeVoucherFromParams, 
    queryNotice, queryReport, queryVoucher, GraphqlOptions
} from "cartesi-client";

/**
 * Configs
 */

const ajv = new Ajv();
addFormats(ajv);
ajv.addFormat("biginteger", (data) => {
    const dataTovalidate = data.startsWith('-') ? data.substring(1) : data;
    return ethers.utils.isHexString(dataTovalidate) && dataTovalidate.length % 2 == 0;
});
const abiCoder = new ethers.utils.AbiCoder();
export const CONVENTIONAL_TYPES: Array<string> = ["bytes","hex","str","int","dict","list","tuple","json"];
const MAX_SPLITTABLE_OUTPUT_SIZE = {{ MAX_SPLITTABLE_OUTPUT_SIZE }};


/**
 * Models
 */

export enum IOType {
    report,
    notice,
    voucher,
    mutationPayload,
    queryPayload
}

interface ModelInterface<T> {
    ioType: IOType;
    abiTypes: Array<string>;
    params: Array<string>;
    decoder?(data: CartesiReport | CartesiNotice | CartesiVoucher | InspectReport): T;
    exporter?(data: T): string;
    validator: ValidateFunction<T>;
}

export interface Models {
    [key: string]: ModelInterface<any>;
}

export interface InspectReportInput {
    index?: number;
}

export interface InspectReport {
    payload: string;
    input?: InspectReportInput;
    index?: number;
}

export interface OutputGetters {
    [key: string]: (o?: GraphqlOptions) => Promise<CartesiReport>|Promise<CartesiNotice>|Promise<CartesiVoucher>;
}

export const outputGetters: OutputGetters = {
    report: queryReport,
    notice: queryNotice,
    voucher: queryVoucher
}

export interface MutationOptions extends AdvanceInputOptions {
    decode?: boolean;
}

export interface QueryOptions extends InspectOptions {
    decode?: boolean;
    decodeModel?: string;
}

export class IOData<T extends object> {
    [key: string]: any;
    _model: ModelInterface<T>

    constructor(model: ModelInterface<T>, data: T, validate: boolean = true) {
        this._model = model;
        for (const key of this._model.params) {
            this[key] = (data as any)[key];
        }
        if (validate) this.validate();
    }

    get = (): T => {
        const data: any = {};
        for (const key of this._model.params) {
            data[key] = this[key];
        }
        return data;
    }

    validate = (): boolean => {
        const dataToValidate: any = { ...this.get() };
        for (const k of Object.keys(dataToValidate)) {
            if (ethers.BigNumber.isBigNumber(dataToValidate[k]))
                dataToValidate[k] = dataToValidate[k].toHexString();
        }
        if (!this._model.validator(dataToValidate))
            throw new Error(`Data does not implement interface: ${ajv.errorsText(this._model.validator.errors)}`);     
        return true;
    }

    export(excludeParams: string[] = []): string {
        let payload: string;
        switch(this._model.ioType) {
            case IOType.mutationPayload: {
                // parametrize input to url
                const inputData: any = this.get();
                const paramList = Array<any>();
                for (const key of this._model.params) {
                    paramList.push(inputData[key]);
                }
                payload = abiCoder.encode(this._model.abiTypes,paramList);
                break;
            }
            case IOType.queryPayload: {
                // parametrize input to url
                const inputData: T = this.get();
                const paramList = Array<string>();
                for (const key in inputData) {
                    if (inputData[key] == undefined) continue;
                    if (excludeParams.indexOf(key) > -1) continue;
                    if (Array.isArray(inputData[key])) {
                        for (const element in inputData[key]) {
                            paramList.push(`${key}=${inputData[key][element]}`);
                        }
                    } else {
                        paramList.push(`${key}=${inputData[key]}`);
                    }
                }
                payload = paramList.length > 0 ? `?${paramList.join('&')}` : "";
                break;
            }
            default: {
                throw new Error(`Invalid payload type ${this._model.ioType}`);
                // break;
            }
        }
        return payload;
    }
}

export class BasicOutput<T extends object> extends IOData<T> {
    _payload: string
    _inputIndex?: number
    _outputIndex?: number

    constructor(model: ModelInterface<T>, payload: string, inputIndex?: number, outputIndex?: number) {
        super(model,genericDecodeTo<T>(payload,model),false);
        this._inputIndex = inputIndex;
        this._outputIndex = outputIndex;
        this._payload = payload;
    }
}

export class Output<T extends object> extends BasicOutput<T>{
    constructor(model: ModelInterface<T>, report: CartesiReport | InspectReport) {
        super(model, report.payload, report.input?.index, report.index);
    }
}

export class OutputWithProof<T extends object> extends BasicOutput<T>{
    _proof: Maybe<Proof> | undefined
    _inputIndex: number
    _outputIndex: number
    
    constructor(model: ModelInterface<T>, payload: string, inputIndex: number, outputIndex: number, proof: Maybe<Proof> | undefined) {
        super(model, payload, inputIndex, outputIndex);
        this._inputIndex = inputIndex;
        this._outputIndex = outputIndex;
        this._proof = proof;
    }
}

export class Event<T extends object> extends OutputWithProof<T>{
    constructor(model: ModelInterface<T>, notice: CartesiNotice) {
        super(model, notice.payload, notice.input.index, notice.index, notice.proof);
    }
    validateOnchain = async (signer: Signer, dappAddress: string): Promise<boolean> => {
        if (this._proof == undefined)
            throw new Error("Notice has no proof");
        return await validateNoticeFromParams(signer,dappAddress,this._payload,this._proof);
    }
}

export class ContractCall<T extends object> extends OutputWithProof<T>{
    _destination: string
    constructor(model: ModelInterface<T>, voucher: CartesiVoucher) {
        super(model, voucher.payload, voucher.input.index, voucher.index, voucher.proof);
        this._destination = voucher.destination;
    }
    wasExecuted = async (signer: Signer, dappAddress: string): Promise<boolean> => {
        return await wasVoucherExecutedFromParams(signer,dappAddress,this._inputIndex,this._outputIndex);
    }
    execute = async (signer: Signer, dappAddress: string): Promise<ContractReceipt | null> => {
        if (this._proof == undefined)
            throw new Error("Voucher has no proof");
        return await executeVoucherFromParams(signer,dappAddress,this._destination,this._payload,this._proof);
    }
}


/*
 * Helpers
 */

// Advance
export async function genericAdvanceInput<T extends object>(
    client:Signer,
    dappAddress:string,
    selector:string,
    inputData: IOData<T>,
    options?:AdvanceInputOptions
):Promise<AdvanceOutput|ContractReceipt> {
    if (options == undefined) options = {};

    const payloadHex = inputData.export();
    const output = await advanceInput(client,dappAddress,selector + payloadHex.replace('0x',''),options).catch(
        e => {
            if (String(e.message).startsWith('0x'))
                throw new Error(ethers.utils.toUtf8String(e.message));
            throw new Error(e.message);
    });

    return output;
}

// Inspect
export async function inspectCall(
    payload:string,
    options:InspectOptions
):Promise<InspectReport> {
    options.decodeTo = "no-decode";
    const inspectResult: string = await inspect(payload,options).catch(
        e => {
            if (String(e.message).startsWith('0x'))
                throw new Error(ethers.utils.toUtf8String(e.message));
            throw new Error(e.message);
    }) as string; // hex string
    return {payload:inspectResult};
}

export async function genericInspect<T extends object>(
    inputData: IOData<T>,
    route: string,
    options?:InspectOptions
):Promise<InspectReport> {
    if (options == undefined) options = {};
    options.aggregate = true;
    const excludeParams: string[] = [];
    const matchRoute = route.matchAll(/\{(\w+)\}/g);
    for (const m of matchRoute) {
        route.replace(m[0],inputData[m[0]]);
        excludeParams.push(m[1]);
    }
    const payload = `${route}${inputData.export()}`
    return await inspectCall(payload,options);
}

// Decode
export function genericDecodeTo<T extends object>(data: string,model: ModelInterface<T>): T {
    let dataObj: any;
    switch(model.ioType) {
        /*# case mutationPayload: {
            break;
        }
        case queryPayload: {
            break;
        }*/
        case IOType.report: {
            const dataStr = ethers.utils.toUtf8String(data);
            try {
                dataObj = JSON.parse(dataStr);
            } catch(e) {
                throw new Error(dataStr);
            }
            dataObj = JSON.parse(ethers.utils.toUtf8String(data));
            if (!model.validator(dataObj))
                throw new Error(`Data does not implement interface: ${ajv.errorsText(model.validator.errors)}`);     
            break;
        }
        case IOType.notice: {
            const dataValues = abiCoder.decode(model.abiTypes,data);
            dataObj = {};
            let ind = 0;
            for (const key of model.params) {
                dataObj[key] = dataValues[ind];
                ind++;
            }
            const dataToValidate = { ...dataObj };
            for (const k of Object.keys(dataToValidate)) {
                if (ethers.BigNumber.isBigNumber(dataToValidate[k]))
                    dataToValidate[k] = dataToValidate[k].toHexString();
            }
            if (!model.validator(dataToValidate))
                throw new Error(`Data does not implement interface: ${ajv.errorsText(model.validator.errors)}`);     
            
            break;
        }
        case IOType.voucher: {
            const abiTypes: Array<string> = ["bytes4"].concat(model.abiTypes);
            const dataValues = abiCoder.decode(abiTypes,data);
            dataObj = {};
            let ind = 0;
            for (const key of model.params) {
                if (ind == 0) continue; // skip selector
                dataObj[key] = dataValues[ind-1];
                ind++;
            }
            const dataToValidate = { ...dataObj };
            for (const k of Object.keys(dataToValidate)) {
                if (ethers.BigNumber.isBigNumber(dataToValidate[k]))
                    dataToValidate[k] = dataToValidate[k].toHexString();
            }
            if (!model.validator(dataToValidate))
                throw new Error(`Data does not implement interface: ${ajv.errorsText(model.validator.errors)}`);
            break;
        }
        default: {
            throw new Error(`Cannot convert ${model.ioType}`);
            // break;
        }
    }
    return dataObj;
}

export function decodeToConventionalTypes(data: string,modelName: string): any {
    if (!CONVENTIONAL_TYPES.includes(modelName))
        throw new Error(`Cannot decode to ${modelName}`);
    switch(modelName) {
        case "bytes": {
            if (typeof data == "string") {
                if (ethers.utils.isHexString(data))
                    return ethers.utils.arrayify(data);
                else
                    throw new Error(`Cannot decode to bytes`);
            }
            return data;
        }
        case "hex": {
            return data;
        }
        case "str": {
            return ethers.utils.toUtf8String(data);
        }
        case "int": {
            if (typeof data == "string") {
                if (ethers.utils.isHexString(data))
                    return parseInt(data, 16);
                else
                    throw new Error(`Cannot decode to int`);
            }
            if (ethers.utils.isBytes(data))
                return parseInt(ethers.utils.hexlify(data), 16);
            else
                throw new Error(`Cannot decode to int`);
        }
        case "dict": case "list": case "tuple": case "json": {
            return JSON.parse(ethers.utils.toUtf8String(data));
        }
    }
}

'''
cartesapp_lib_template = '''
/* eslint-disable */
/**
 * This file was automatically generated by cartesapp.template_generator.
 * DO NOT MODIFY IT BY HAND. Instead, run the generator,
 */

import { 
    advanceInput, inspect, 
    AdvanceOutput, InspectOptions, AdvanceInputOptions, GraphqlOptions,
    Report as CartesiReport, Notice as CartesiNotice, Voucher as CartesiVoucher, 
    advanceDAppRelay, advanceERC20Deposit, advanceERC721Deposit, advanceEtherDeposit,
    queryNotice, queryReport, queryVoucher
} from "cartesi-client";

import { 
    InspectReport, outputGetters
} from "../cartesapp/utils"

{% if add_indexer_query -%}
import * as indexerIfaces from "../indexer/ifaces";
import * as indexerLib from "../indexer/lib"
{% endif %}



{% if add_indexer_query -%}

interface OutMap {
    [key: string]: CartesiReport | CartesiNotice | CartesiVoucher;
}
type outType = "report" | "notice" | "voucher";
type AdvanceOutputMap = Record<outType,OutMap>

export async function decodeAdvance(
    advanceResult: AdvanceOutput,
    decoder: (data: CartesiReport | CartesiNotice | CartesiVoucher | InspectReport, modelName:string) => any,
    options?:InspectOptions): Promise<any[]>
{
    let input_index:number;
    if (advanceResult.reports.length > 0) {
        input_index = advanceResult.reports[0].input.index;
    } else if (advanceResult.notices.length > 0) {
        input_index = advanceResult.notices[0].input.index;
    } else if (advanceResult.vouchers.length > 0) {
        input_index = advanceResult.vouchers[0].input.index;
    } else {
        // Can't decode outputs (no outputs)
        return [];
    }
    const outMap: AdvanceOutputMap = {report:{},notice:{},voucher:{}};
    for (const report of advanceResult.reports) { outMap.report[report.index] = report }
    for (const notice of advanceResult.notices) { outMap.notice[notice.index] = notice }
    for (const voucher of advanceResult.vouchers) { outMap.voucher[voucher.index] = voucher }

    const indexerOutput: indexerLib.{{ indexer_output_info['model'].__name__ }} = await indexerLib.{{ convert_camel_case(indexer_query_info['method']) }}({input_index:input_index},{...options, decode:true, decodeModel:"{{ indexer_output_info['model'].__name__ }}"}) as indexerLib.{{ indexer_output_info['model'].__name__ }};

    const outList: any[] = [];
    for (const indOut of indexerOutput.data) {
        outList.push( decoder(outMap[indOut.output_type as outType][`${indOut.output_index}`],indOut.class_name) );
    }
    return outList
}

// indexer
export async function genericGetOutputs(
    inputData: indexerIfaces.{{ indexer_query_info['model'].__name__ }},
    decoder: (data: CartesiReport | CartesiNotice | CartesiVoucher | InspectReport, modelName:string) => any,
    options?:InspectOptions
):Promise<any[]> {
    if (options == undefined) options = {};
    const indexerOutput: indexerLib.{{ indexer_output_info['model'].__name__ }} = await indexerLib.{{ convert_camel_case(indexer_query_info['method']) }}(inputData,{...options, decode:true, decodeModel:"{{ indexer_output_info['model'].__name__ }}"}) as indexerLib.{{ indexer_output_info['model'].__name__ }};
    const graphqlQueries: Promise<any>[] = [];
    for (const outInd of indexerOutput.data) {
        const graphqlOptions: GraphqlOptions = {cartesiNodeUrl: options.cartesiNodeUrl, inputIndex: outInd.input_index, outputIndex: outInd.output_index};
        graphqlQueries.push(outputGetters[outInd.output_type](graphqlOptions).then(
            (output: CartesiReport | CartesiNotice | CartesiVoucher | InspectReport) => {
                return decoder(output,outInd.class_name);
            }
        ));
    }
    return Promise.all(graphqlQueries);
}
{% endif %}

'''

lib_template_std_imports = '''/* eslint-disable */
/**
 * This file was automatically generated by cartesapp.template_generator.
 * DO NOT MODIFY IT BY HAND. Instead, run the generator,
 */
import { ethers, Signer, ContractReceipt } from "ethers";

import { 
    advanceInput, inspect, 
    AdvanceOutput, InspectOptions, AdvanceInputOptions, GraphqlOptions,
    EtherDepositOptions, ERC20DepositOptions, ERC721DepositOptions,
    Report as CartesiReport, Notice as CartesiNotice, Voucher as CartesiVoucher, 
    advanceDAppRelay, advanceERC20Deposit, advanceERC721Deposit, advanceEtherDeposit,
    queryNotice, queryReport, queryVoucher
} from "cartesi-client";

'''

lib_template = '''
import Ajv from "ajv"
import addFormats from "ajv-formats"

import { 
    genericAdvanceInput, genericInspect, IOType, Models,
    IOData, Output, Event, ContractCall, InspectReport, 
    MutationOptions, QueryOptions, 
    CONVENTIONAL_TYPES, decodeToConventionalTypes
} from "../cartesapp/utils"

{% if has_indexer_query -%}
import { 
    genericGetOutputs, decodeAdvance
} from "../cartesapp/lib"

import * as indexerIfaces from "../indexer/ifaces"
{% endif -%}

import * as ifaces from "./ifaces";


/**
 * Configs
 */

const ajv = new Ajv();
addFormats(ajv);
ajv.addFormat("biginteger", (data) => {
    const dataTovalidate = data.startsWith('-') ? data.substring(1) : data;
    return ethers.utils.isHexString(dataTovalidate) && dataTovalidate.length % 2 == 0;
});
const MAX_SPLITTABLE_OUTPUT_SIZE = {{ MAX_SPLITTABLE_OUTPUT_SIZE }};

/*
 * Mutations/Advances
 */

{% for info in mutations_info -%}
export async function {{ convert_camel_case(info['method']) }}(
    client:Signer,
    dappAddress:string,
    inputData: ifaces.{{ convert_camel_case(info['model'].__name__,True) }},
    options?:MutationOptions
):Promise<AdvanceOutput|ContractReceipt|any[]> {
    const data: {{ convert_camel_case(info['model'].__name__,True) }} = new {{ convert_camel_case(info['model'].__name__,True) }}(inputData);
    {% if has_indexer_query -%}
    if (options?.decode) { options.sync = true; }
    const result = await genericAdvanceInput<ifaces.{{ convert_camel_case(info['model'].__name__,True) }}>(client,dappAddress,'{{ "0x"+info["selector"].to_bytes().hex() }}',data, options)
    if (options?.decode) {
        return decodeAdvance(result as AdvanceOutput,decodeToModel,options);
    }
    return result;
{% else -%}
    return genericAdvanceInput<ifaces.{{ convert_camel_case(info['model'].__name__,True) }}>(client,dappAddress,'{{ "0x"+info["selector"].to_bytes().hex() }}',data, options);
{% endif -%}
}

{% endfor %}
/*
 * Queries/Inspects
 */

{% for info in queries_info -%}
export async function {{ convert_camel_case(info['method']) }}(
    inputData: ifaces.{{ convert_camel_case(info['model'].__name__,True) }},
    options?:QueryOptions
):Promise<InspectReport|any> {
    const route = '{{ info["selector"] }}';
    {# return genericInspect<ifaces.{{ convert_camel_case(info['model'].__name__,True) }}>(data,route,options); -#}
    {% if info["configs"].get("splittable_output") -%}
    let part:number = 0;
    let hasMoreParts:boolean = false;
    const output: InspectReport = {payload: "0x"}
    do {
        hasMoreParts = false;
        let inputDataSplittable = Object.assign({part},inputData);
        const data: {{ convert_camel_case(info['model'].__name__,True) }} = new {{ convert_camel_case(info['model'].__name__,True) }}(inputDataSplittable);
        const partOutput: InspectReport = await genericInspect<ifaces.{{ convert_camel_case(info['model'].__name__,True) }}>(data,route,options);
        let payloadHex = partOutput.payload.substring(2);
        if (payloadHex.length/2 > MAX_SPLITTABLE_OUTPUT_SIZE) {
            part++;
            payloadHex = payloadHex.substring(0, payloadHex.length - 2);
            hasMoreParts = true;
        }
        output.payload += payloadHex;
    } while (hasMoreParts)
    {% else -%}
    const data: {{ convert_camel_case(info['model'].__name__,True) }} = new {{ convert_camel_case(info['model'].__name__,True) }}(inputData);
    const output: InspectReport = await genericInspect<ifaces.{{ convert_camel_case(info['model'].__name__,True) }}>(data,route,options);
    {% endif -%}
    if (options?.decode) { return decodeToModel(output,options.decodeModel || "json"); }
    return output;
}

{% endfor %}
{% if has_indexer_query -%}
/*
 * Indexer Query
 */

export async function getOutputs(
    inputData: indexerIfaces.IndexerPayload,
    options?:InspectOptions
):Promise<any[]> {
    return genericGetOutputs(inputData,decodeToModel,options);
}
{% endif %}

/**
 * Models Decoders/Exporters
 */

export function decodeToModel(data: CartesiReport | CartesiNotice | CartesiVoucher | InspectReport, modelName: string): any {
    if (modelName == undefined)
        throw new Error("undefined model");
    if (CONVENTIONAL_TYPES.includes(modelName))
        return decodeToConventionalTypes(data.payload,modelName);
    const decoder = models[modelName].decoder;
    if (decoder == undefined)
        throw new Error("undefined decoder");
    return decoder(data);
}

export function exportToModel(data: any, modelName: string): string {
    const exporter = models[modelName].exporter;
    if (exporter == undefined)
        throw new Error("undefined exporter");
    return exporter(data);
}

{% for info in mutations_payload_info -%}
export class {{ convert_camel_case(info['model'].__name__,True) }} extends IOData<ifaces.{{ convert_camel_case(info['model'].__name__,True) }}> { constructor(data: ifaces.{{ info["model"].__name__ }}, validate: boolean = true) { super(models['{{ info["model"].__name__ }}'],data,validate); } }
export function exportTo{{ convert_camel_case(info['model'].__name__,True) }}(data: ifaces.{{ info["model"].__name__ }}): string {
    const dataToExport: {{ convert_camel_case(info['model'].__name__,True) }} = new {{ convert_camel_case(info['model'].__name__,True) }}(data);
    return dataToExport.export();
}

{% endfor -%}
{% for info in queries_payload_info -%}
export class {{ convert_camel_case(info['model'].__name__,True) }} extends IOData<ifaces.{{ convert_camel_case(info['model'].__name__,True) }}> { constructor(data: ifaces.{{ info["model"].__name__ }}, validate: boolean = true) { super(models['{{ info["model"].__name__ }}'],data,validate); } }
export function exportTo{{ convert_camel_case(info['model'].__name__,True) }}(data: ifaces.{{ info["model"].__name__ }}): string {
    const dataToExport: {{ convert_camel_case(info['model'].__name__,True) }} = new {{ convert_camel_case(info['model'].__name__,True) }}(data);
    return dataToExport.export();
}

{% endfor -%}
{% for info in reports_info -%}
export class {{ convert_camel_case(info['class'],True) }} extends Output<ifaces.{{ convert_camel_case(info['class'],True) }}> { constructor(output: CartesiReport | InspectReport) { super(models['{{ info["class"] }}'],output); } }
export function decodeTo{{ convert_camel_case(info['class'],True) }}(output: CartesiReport | CartesiNotice | CartesiVoucher | InspectReport): {{ convert_camel_case(info['class'],True) }} {
    return new {{ convert_camel_case(info['class'],True) }}(output as CartesiReport);
}

{% endfor -%}
{% for info in notices_info -%}
export class {{ convert_camel_case(info['class'],True) }} extends Event<ifaces.{{ convert_camel_case(info['class'],True) }}> { constructor(output: CartesiNotice) { super(models['{{ info["class"] }}'],output); } }
export function decodeTo{{ convert_camel_case(info['class'],True) }}(output: CartesiReport | CartesiNotice | CartesiVoucher | InspectReport): {{ convert_camel_case(info['class'],True) }} {
    return new {{ convert_camel_case(info['class'],True) }}(output as CartesiNotice);
}

{% endfor -%}
{% for info in vouchers_info -%}
export class {{ convert_camel_case(info['class'],True) }} extends ContractCall<ifaces.{{ convert_camel_case(info['class'],True) }}> { constructor(output: CartesiVoucher) { super(models['{{ info["class"] }}'],output); } }
export function decodeTo{{ convert_camel_case(info['class'],True) }}(output: CartesiReport | CartesiNotice | CartesiVoucher | InspectReport): {{ convert_camel_case(info['class'],True) }} {
    return new {{ convert_camel_case(info['class'],True) }}(output as CartesiVoucher);
}

{% endfor %}
/**
 * Model
 */

export const models: Models = {
    {% for info in mutations_payload_info -%}
    '{{ info["model"].__name__ }}': {
        ioType:IOType.mutationPayload,
        abiTypes:{{ info['abi_types'] }},
        params:{{ list(info["model"].__fields__.keys()) }},
        exporter: exportTo{{ info["model"].__name__ }},
        validator: ajv.compile<ifaces.{{ info["model"].__name__ }}>(JSON.parse('{{ info["model"].schema_json() }}'))
    },
    {% endfor -%}
    {% for info in queries_payload_info -%}
    '{{ info["model"].__name__ }}': {
        ioType:IOType.queryPayload,
        abiTypes:{{ info['abi_types'] }},
        params:{{ list(info["model"].__fields__.keys()) }},
        exporter: exportTo{{ info["model"].__name__ }},
        validator: ajv.compile<ifaces.{{ info["model"].__name__ }}>(JSON.parse('{{ info["model"].schema_json() }}'))
    },
    {% endfor -%}
    {% for info in reports_info -%}
    '{{ info["class"] }}': {
        ioType:IOType.report,
        abiTypes:{{ info['abi_types'] }},
        params:{{ list(info["model"].__fields__.keys()) }},
        decoder: decodeTo{{ convert_camel_case(info['class'],True) }},
        validator: ajv.compile<ifaces.{{ convert_camel_case(info['class'],True) }}>(JSON.parse('{{ info["model"].schema_json() }}'))
    },
    {% endfor -%}
    {% for info in notices_info -%}
    '{{ info["class"] }}': {
        ioType:IOType.notice,
        abiTypes:{{ info['abi_types'] }},
        params:{{ list(info["model"].__fields__.keys()) }},
        decoder: decodeTo{{ convert_camel_case(info['class'],True) }},
        validator: ajv.compile<ifaces.{{ convert_camel_case(info['class'],True) }}>(JSON.parse('{{ info["model"].schema_json() }}'.replaceAll('integer','string","format":"biginteger')))
    },
    {% endfor -%}
    {% for info in vouchers_info -%}
    '{{ info["class"] }}': {
        ioType:IOType.voucher,
        abiTypes:{{ info['abi_types'] }},
        params:{{ list(info["model"].__fields__.keys()) }},
        decoder: decodeTo{{ convert_camel_case(info['class'],True) }},
        validator: ajv.compile<ifaces.{{ convert_camel_case(info['class'],True) }}>(JSON.parse('{{ info["model"].schema_json() }}'.replaceAll('integer','string","format":"biginteger')))
    },
    {% endfor -%}
};
'''