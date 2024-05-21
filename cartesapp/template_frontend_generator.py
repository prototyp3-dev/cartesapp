from pydantic2ts.cli.script import generate_json_schema
import os
import json
import subprocess
import tempfile
from jinja2 import Template
from packaging.version import Version
import re
from .templates import cartesapp_lib_template, cartesapp_utils_template, lib_template, lib_template_std_imports

from .output import MAX_SPLITTABLE_OUTPUT_SIZE

FRONTEND_PATH = 'frontend'
DEFAULT_LIB_PATH = 'src'
PACKAGES_JSON_FILENAME = "package.json"
TSCONFIG_JSON_FILENAME = "tsconfig.json"

def convert_camel_case(s, title_first = False):
    snaked = re.sub(r'(?<!^)(?=[A-Z])', '_', s).lower() 
    splitted = snaked.split('_')
    return (splitted[0] if not title_first else splitted[0].title()) + ''.join(i.title() for i in splitted[1:])

def render_templates(settings,mutations_info,queries_info,notices_info,reports_info,vouchers_info,modules_to_add,**kwargs):
    defaultKwargs = { 'libs_path': DEFAULT_LIB_PATH, 'frontend_path': FRONTEND_PATH }
    kwargs = { **defaultKwargs, **kwargs }
    frontend_path = kwargs.get('frontend_path')
    libs_path = kwargs.get('libs_path')

    add_indexer_query = False
    add_dapp_relay = False
    add_wallet = False
    for module_name in settings:
        if not add_indexer_query and hasattr(settings[module_name],'INDEX_OUTPUTS') and getattr(settings[module_name],'INDEX_OUTPUTS'): 
            add_indexer_query = True
        if not add_indexer_query and hasattr(settings[module_name],'INDEX_INPUTS') and getattr(settings[module_name],'INDEX_INPUTS'): 
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

    cartesapppath = f"{frontend_path}/{libs_path}/cartesapp"
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

        mutations_payload_info  = [dict(p) for p in set([(("abi_types",tuple(i["abi_types"])),("model",i["model"]),("has_proxy",i["configs"].get("proxy") is not None)) for i in module_mutations_info])]
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

        frontend_lib_path = f"{frontend_path}/{libs_path}/{module_name}"

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


def create_frontend_structure(**kwargs):
    defaultKwargs = { 'libs_path': DEFAULT_LIB_PATH, 'frontend_path': FRONTEND_PATH }
    kwargs = { **defaultKwargs, **kwargs }
    frontend_path = kwargs.get('frontend_path')
    # packages json
    pkg_path = f"{frontend_path}/{PACKAGES_JSON_FILENAME}"
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
    tscfg_path = f"{frontend_path}/{TSCONFIG_JSON_FILENAME}"
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



    if not os.path.exists(frontend_path):
        os.makedirs(frontend_path)

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
        "ethers": "<6"
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
        "target": "es2021",
        "moduleResolution": "node",
        # "plugins": [
        #     { "transform": "ts-transformer-keys/transformer" }
        # ]
    }
}
