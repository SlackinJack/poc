# the file holds the global configurations objects


import json


from modules.file.operation import readFile
from modules.util.strings.paths import CONFIGS_FILE_NAME, CONFIGS_PATH
from modules.util.strings.paths import MODELS_CONFIG_FILE_NAME


__configs = {}  # main configuration
__modelConfigs = {}  # model configuration
__configurationFileName = CONFIGS_FILE_NAME
__defaultModelName = ""


def getConfig(keyIn):
    return __configs[keyIn]


def setConfig(keyIn, settingIn):
    global __configs
    __configs[keyIn] = settingIn
    return


def resetConfig():
    global __configs
    __configs = {}
    return


# unused
def getModelConfig(keyIn):
    return __modelConfigs[keyIn]


def getModelConfigAll():
    return __modelConfigs


def setModelConfig(keyIn, settingIn):
    global __modelConfigs
    __modelConfigs[keyIn] = settingIn
    return


def resetModelConfig():
    global __modelConfigs
    __modelConfigs = {}
    return


def loadConfiguration():
    resetConfig()
    newConfig = json.loads(
        readFile(CONFIGS_PATH + __configurationFileName, None)
    )
    for k, v in newConfig.items():
        if not k.endswith("_desc") and not k.endswith("_section"):
            setConfig(k, v)

    if not getConfig("address").endswith("/v1"):
        newAddress = getConfig("address")
        if not newAddress.endswith("/"):
            newAddress += "/"
        setConfig("address", newAddress + "v1")
    return


def loadModelConfiguration():
    resetModelConfig()
    newModelConfig = json.loads(
        readFile(CONFIGS_PATH + MODELS_CONFIG_FILE_NAME, None)
    )
    for k, v in newModelConfig.items():
        setModelConfig(k, v)
    return


def setDefaultTextModel(modelNameIn):
    global __defaultModelName
    __defaultModelName = modelNameIn
    return


def resetDefaultTextModel():
    setConfig("default_text_to_text_model", __defaultModelName)
    return


def setConfigurationFileName(configurationFileNameIn):
    global __configurationFileName
    __configurationFileName = configurationFileNameIn
    return


def getConfigurationFileName():
    return __configurationFileName
