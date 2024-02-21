
import logging

from cartesapp.manager import Manager

logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
    app_manager = Manager()
    app_manager.add_module('app')
    app_manager.run()
