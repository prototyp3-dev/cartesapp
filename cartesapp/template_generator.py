import os
import json
import tempfile
import logging
from jinja2 import Template
from importlib.resources import files
from pydantic2ts.cli.script import _generate_json_schema as generate_json_schema
from packaging.version import Version
from cartesapp.external_tools import communicate_cmd

from cartesapp.utils import convert_camel_case

from cartesapp.output import MAX_SPLITTABLE_OUTPUT_SIZE

LOGGER = logging.getLogger(__name__)

FRONTEND_PATH = 'frontend'
DEFAULT_LIB_PATH = os.path.join('src','lib')
PACKAGES_JSON_FILENAME = "package.json"

def render_templates(settings,mutations_info,queries_info,notices_info,reports_info,vouchers_info,modules_to_add,**kwargs):
    defaultKwargs = { 'libs_path': DEFAULT_LIB_PATH, 'frontend_path': FRONTEND_PATH }
    kwargs = { **defaultKwargs}|{**kwargs }
    frontend_path = kwargs.get('frontend_path')
    if frontend_path is None: raise Exception("No frontend path provided")
    libs_path = kwargs.get('libs_path')
    if libs_path is None: raise Exception("No libs path provided")
    generate_debug_components = kwargs.get('generate_debug_components')

    add_indexer_query = False
    add_dapp_relay = False
    add_wallet = False
    for module_name in settings:
        if not add_indexer_query and hasattr(settings[module_name],'INDEX_OUTPUTS') and getattr(settings[module_name],'INDEX_OUTPUTS'):
            add_indexer_query = True
        if not add_indexer_query and hasattr(settings[module_name],'INDEX_INPUTS') and getattr(settings[module_name],'INDEX_INPUTS'):
            add_indexer_query = True
        if not add_wallet and hasattr(settings[module_name],'ENABLE_WALLET') and getattr(settings[module_name],'ENABLE_WALLET'):
            add_wallet = True
        if add_indexer_query and add_dapp_relay and add_wallet:
            break


    modules = modules_to_add.copy()

    template_content = files('cartesapp.__templates__').joinpath('cartesapp-utils.ts.jinja').read_text()
    helper_template_output = Template(template_content).render()

    cartesapppath = os.path.join(frontend_path,libs_path,"cartesapp")
    if not os.path.exists(cartesapppath):
        os.makedirs(cartesapppath)

    with open(os.path.join(cartesapppath,"utils.ts"), "w") as f:
        f.write(helper_template_output)

    template_content = files('cartesapp.__templates__').joinpath('cartesapp-inspect.ts.jinja').read_text()
    helper_template_output = Template(template_content).render()

    with open(os.path.join(cartesapppath,"inspect.ts"), "w") as f:
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
        template_content = files('cartesapp.__templates__').joinpath('cartesapp-lib.ts.jinja').read_text()
        helper_lib_template_output = Template(template_content).render({
            "convert_camel_case":convert_camel_case,
            "add_indexer_query": add_indexer_query,
            "add_dapp_relay": add_dapp_relay,
            "indexer_query_info": indexer_query_info,
            "indexer_output_info": indexer_output_info,
            "MAX_SPLITTABLE_OUTPUT_SIZE":MAX_SPLITTABLE_OUTPUT_SIZE
        })

        with open(os.path.join(cartesapppath,"lib.ts"), "w") as f:
            f.write(helper_lib_template_output)


    all_modules = {}
    modules_processed = []
    while len(modules) > 0:
        module_name = modules.pop()
        modules_processed.append(module_name)

        module_notices_info = [i for i in notices_info.values() if i['module'] == module_name]
        module_reports_info = [i for i in reports_info.values() if i['module'] == module_name]
        module_vouchers_info = [i for i in vouchers_info.values() if i['module'] == module_name]
        module_mutations_info = [i for i in mutations_info.values() if i['module'] == module_name and i['configs'].get('specialized_template') is None]
        module_queries_info = [i for i in queries_info.values() if i['module'] == module_name]

        classes_added = []
        mutations_payload_info  = []
        for i in module_mutations_info:
            if i['model'].__name__ not in classes_added:
                mutations_payload_info.append(dict((("abi_types",tuple(i["abi_types"])),("model",i["model"]),("has_proxy",i["configs"].get("proxy") is not None))))
                classes_added.append(i['model'].__name__)

        for i in mutations_payload_info: i["abi_types"] = list(i["abi_types"])
        classes_added = []
        queries_payload_info  = []
        for i in module_queries_info:
            if i['model'].__name__ not in classes_added:
                queries_payload_info.append(dict((("abi_types",tuple(i["abi_types"])),("model",i["model"]),("query_type",i["query_type"]))))
                classes_added.append(i['model'].__name__)

        for i in queries_payload_info: i["abi_types"] = list(i["abi_types"])

        models = []
        models.extend(map(lambda i:i['model'],module_notices_info))
        models.extend(map(lambda i:i['model'],module_reports_info))
        models.extend(map(lambda i:i['model'],module_vouchers_info))
        models.extend(map(lambda i:i['model'],module_mutations_info))
        models.extend(map(lambda i:i['model'],module_queries_info))
        models = list(set(models))

        frontend_lib_path = os.path.join(frontend_path,libs_path,module_name)

        filepath = f"{frontend_lib_path}/lib.ts"

        specialized_templates = ''
        for i in mutations_info.values():
            if i['module'] == module_name and i['configs'].get('specialized_template'):
                specialized_templates += i['configs'].get('specialized_template')

        # if len(models) > 0 or len(specialized_templates) > 0:
        #     if not os.path.exists(frontend_lib_path):
        #         os.makedirs(frontend_lib_path)

        #     with open(filepath, "w") as f:
        #         template_content = files('cartesapp.__templates__').joinpath('module-imports-lib.ts.jinja').read_text()
        #         f.write(template_content)

        if len(models) > 0:
            if not os.path.exists(frontend_lib_path):
                os.makedirs(frontend_lib_path)
            # print(models)
            # # mod = types.ModuleType(module_name)
            # # mod.NOTICE_FORMAT = "header_abi"
            # # raise Exception("EXIT!")
            # generate_typescript_defs(module_name,os.path.join(frontend_lib_path,"ifaces.d.ts"))
            schema = generate_json_schema(models)

            output_filepath = f"{frontend_lib_path}/ifaces.d.ts"

            schema_temp = tempfile.NamedTemporaryFile()
            schema_file_path = schema_temp.name

            with open(schema_file_path, "w") as f:
                f.write(schema)

            args = ["npx","json-schema-to-typescript"]
            args.extend(["-i",schema_file_path])
            args.extend(["-o",output_filepath])

            stdout, stderr = communicate_cmd(args,force_host=True)
            if stdout:
                LOGGER.debug(stdout)
            if stderr:
                msg = f"Error generating typescript interfaces: {str(stderr)}"
                LOGGER.error(msg)
                schema_temp.close()
                raise Exception(msg)

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

            template_content = files('cartesapp.__templates__').joinpath('module-lib.ts.jinja').read_text()
            lib_template_output = Template(template_content).render({
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

            with open(filepath, "w") as f:
                f.write(lib_template_output)
            all_modules[module_name] = {
                "has_indexer_query":has_indexer_query,
                "mutations_info":module_mutations_info,
                "queries_info":module_queries_info,
                "notices_info":module_notices_info,
                "reports_info":module_reports_info,
                "vouchers_info":module_vouchers_info,
            }
    if generate_debug_components:
        src_path = os.path.dirname(libs_path.rstrip(os.path.sep))
        base_dir = os.path.basename(libs_path.rstrip(os.path.sep))
        frontend_lib_path = os.path.join(frontend_path,src_path)

        # portals
        if add_wallet:
            filepath = f"{frontend_lib_path}/Portals.tsx"
            template_content = files('cartesapp.__templates__').joinpath('Portals.tsx.jinja').read_text()
            template_output = Template(template_content).render({
                "base_dir":base_dir,
            })
            with open(filepath, "w") as f:
                f.write(template_output)

        # utils
        filepath = f"{frontend_lib_path}/utils.ts"
        template_content = files('cartesapp.__templates__').joinpath('utils.ts.jinja').read_text()
        template_output = Template(template_content).render({
            "base_dir":base_dir,
            "add_indexer_query":add_indexer_query,
        })
        with open(filepath, "w") as f:
            f.write(template_output)

        # app
        filepath = f"{frontend_lib_path}/App.tsx"
        template_content = files('cartesapp.__templates__').joinpath('App.tsx.jinja').read_text()
        template_output = Template(template_content).render({
            "add_wallet":add_wallet,
        })
        with open(filepath, "w") as f:
            f.write(template_output)

        # input
        filepath = f"{frontend_lib_path}/Input.tsx"
        template_content = files('cartesapp.__templates__').joinpath('Input.tsx.jinja').read_text()
        template_output = Template(template_content).render({
            "base_dir":base_dir,
            "all_modules":all_modules,
            "convert_camel_case":convert_camel_case
        })
        with open(filepath, "w") as f:
            f.write(template_output)

        # inspect
        filepath = f"{frontend_lib_path}/Inspect.tsx"
        template_content = files('cartesapp.__templates__').joinpath('Inspect.tsx.jinja').read_text()
        template_output = Template(template_content).render({
            "base_dir":base_dir,
            "all_modules":all_modules,
            "convert_camel_case":convert_camel_case,
            "add_indexer_query":add_indexer_query,
        })
        with open(filepath, "w") as f:
            f.write(template_output)

        # output
        filepath = f"{frontend_lib_path}/Outputs.tsx"
        template_content = files('cartesapp.__templates__').joinpath('Outputs.tsx.jinja').read_text()
        template_output = Template(template_content).render({
            "base_dir":base_dir,
            "all_modules":all_modules,
            "convert_camel_case":convert_camel_case
        })
        with open(filepath, "w") as f:
            f.write(template_output)

        # report
        filepath = f"{frontend_lib_path}/Reports.tsx"
        template_content = files('cartesapp.__templates__').joinpath('Reports.tsx.jinja').read_text()
        template_output = Template(template_content).render({
            "base_dir":base_dir,
            "all_modules":all_modules,
            "convert_camel_case":convert_camel_case
        })
        with open(filepath, "w") as f:
            f.write(template_output)

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
        LOGGER.warning(f"Required package {pkg_name} version is {req_version} but original is {orig_version}: keeping original (fix this manually)")
        return orig_version
    newer = orig_version
    if rv > ov: newer = req_version
    return newer

def create_frontend_structure(**kwargs):
    import shutil
    defaultKwargs = { 'libs_path': DEFAULT_LIB_PATH, 'frontend_path': FRONTEND_PATH }
    kwargs = { **defaultKwargs}|{**kwargs }
    frontend_path = kwargs.get('frontend_path')
    if frontend_path is None: raise Exception("No frontend path provided")
    frontend_path = frontend_path.rstrip(os.path.sep)

    args = ["npx","create-vite"]
    args.append(frontend_path)
    args.extend(["--template","react-ts"])


    stdout, stderr = communicate_cmd(args,force_host=True)
    if stdout:
        LOGGER.debug(stdout)
    if stderr:
        msg = f"Error generating typescript interfaces: {str(stderr)}"
        LOGGER.error(msg)
        raise Exception(msg)

    # packages json
    pkg_path = os.path.join(frontend_path,PACKAGES_JSON_FILENAME)
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
                    LOGGER.warning(f"Required package {key} section is '{packages_json[section][key]}' but original is '{original_pkg[section][key]}': keeping original (fix this manually)")
                original_pkg[section][key] = original_pkg[section].get(key) or packages_json[section][key]

    if not os.path.exists(frontend_path):
        os.makedirs(frontend_path)

    with open(pkg_path, "w") as f:
        json_str = json.dumps(original_pkg, indent=2)
        f.write(json_str)

    # remove unnecessary files
    public_dir = os.path.join(frontend_path,'public')
    if os.path.isdir(public_dir): shutil.rmtree(public_dir)
    readme_file = os.path.join(frontend_path,'README.md')
    if os.path.isfile(readme_file): os.remove(readme_file)

    # index
    filepath = f"{frontend_path}/index.html"
    template_content = files('cartesapp.__templates__').joinpath('index.html.jinja').read_text()
    template_output = Template(template_content).render({})
    with open(filepath, "w") as f:
        f.write(template_output)

def create_cartesapp_module(module_name: str, basedir = '.'):
    module_path = os.path.join(basedir,module_name)
    if os.path.exists(module_path):
        LOGGER.warning(f"Module {module_name} already exists")
        return

    os.makedirs(module_path)
    filepath = f"{module_path}/settings.py"
    template_content = files('cartesapp.__templates__').joinpath('base_settings.py.jinja').read_text()
    template_output = Template(template_content).render({
        "file_name":module_name
    })
    with open(filepath, "w") as f:
        f.write(template_output)

    filepath = f"{module_path}/{module_name}.py"
    template_content = files('cartesapp.__templates__').joinpath('base_app.py.jinja').read_text()
    template_output = Template(template_content).render({})
    with open(filepath, "w") as f:
        f.write(template_output)

    tests_path = os.path.join(basedir,'tests')
    if not os.path.isdir(tests_path): os.makedirs(tests_path)
    filepath = f"{tests_path}/test_{module_name}.py"
    template_content = files('cartesapp.__templates__').joinpath('base_test.py.jinja').read_text()
    template_output = Template(template_content).render({
        "module_name":module_name,
        "file_name":module_name
    })
    with open(filepath, "w") as f:
        f.write(template_output)


packages_json = {
    "scripts": {
        # "dry-run": "ts-node src/dry-run.ts",
        # "prepare": "ts-patch install"
    },
    "dependencies": {
        "viem": "^2.26.2",
        "@cartesi/viem": "2.0.0-alpha.4",
        "ajv": "^8.17.1",
        "ajv-formats": "^3.0.1",
        "@rjsf/core": "6.0.0-beta.7",
        "@rjsf/utils": "6.0.0-beta.7",
        "@rjsf/validator-ajv8": "6.0.0-beta.7",
    },
    "devDependencies": {
    }
}
