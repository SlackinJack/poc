import json


from modules.file.operation import appendFile, deleteFile
from modules.util.configuration import getConfig, getModelConfigAll
from modules.util.configuration import loadModelConfiguration
from modules.util.strings.paths import CONFIGS_PATH, MODELS_CONFIG_FILE_NAME
from modules.util.util import getStringMatchPercentage, checkEmptyString
from modules.util.util import printError, getModelsFromServer, printDump
from modules.util.util import printDebug, printGreen


__modelTypes = {
    "image_to_text": "Image-to-Text"
}


def getModelTypes():
    return __modelTypes


def getModelByName(modelNameIn):
    modelNameIn = modelNameIn.lower()
    for model, data in getModelConfigAll().items():
        m = model.lower()
        if modelNameIn == m:
            return model
    return None


def getModelByNameAndType(nameIn, typeIn, modelOnly, strictMatching, silent):
    modelNameIn = nameIn.lower()
    outModel = ""
    outModelData = None
    modelNames = None
    if " " in modelNameIn:
        modelNames = modelNameIn.split(" ")
    for model, data in getModelConfigAll().items():  # L1
        if data["model_type"].lower() == typeIn:
            m = model.lower()
            if strictMatching:
                if modelNameIn == m:
                    outModel = model
                    outModelData = data
                    break  # L1
            else:
                if modelNames is not None:
                    matchesNames = True
                    for part in modelNames:  # L2
                        if part not in m:
                            matchesNames = False
                            break  # L2
                    if matchesNames and (
                        len(outModel) == 0 or (
                            getStringMatchPercentage(m, modelNameIn) > (
                                getStringMatchPercentage(m, list(outModel)[0])
                            )
                        )
                    ):
                        outModel = model
                        outModelData = data
                elif modelNameIn in m or m in modelNameIn:
                    if len(outModel) == 0 or (
                        getStringMatchPercentage(m, modelNameIn) > (
                            getStringMatchPercentage(m, list(outModel)[0])
                        )
                    ):
                        outModel = model
                        outModelData = data
    if len(outModel) > 0:
        if modelOnly:
            return outModel
        else:
            return {outModel: outModelData}
    else:
        if not silent:
            printError("\nNo model found with name: " + modelNameIn)
        return None


def getModelsWithType(modelTypeIn):
    out = {}
    for model, data in getModelConfigAll().items():
        if data["model_type"].lower() == modelTypeIn:
            out[model] = data
    return out


def getModelDataIfExists(dataNameIn, modelNameIn):
    modelNameIn = modelNameIn.lower()
    for model, data in getModelConfigAll().items():
        if modelNameIn == model.lower():
            if data.get(dataNameIn) is not None and not (
                checkEmptyString(data[dataNameIn])
            ):
                return data[dataNameIn]
            break
    return None


def getModelFromConfiguration(modelToGet, modelType, writeAsCaps):
    model = getModelByNameAndType(modelToGet, modelType, True, False, False)
    if model is None:
        model = getModelByNameAndType("", modelType, True, False, False)
        if writeAsCaps:
            modelType = modelType.upper()
        if "_" in modelType:
            modelType = modelType.replace("_", " ")
        if model is not None:
            printError(
                "\nConfiguration-specified " + modelType + " model not found "
                "- using " + model + "."
            )
        else:
            printError(
                "\nCannot find a(n) " + modelType + " model "
                "- configure a model in order to use this functionality."
            )
    return model


def modelScanner():
    modelList = getModelsFromServer(False)
    if modelList is not None:
        addModels = {}
        for model in modelList:
            if not model["id"] in (
                getConfig("model_scanner_ignored_filenames")
            ) and not model["id"] in getModelConfigAll():
                printDebug(model["id"] + " is missing from model config")
                addModels[model["id"]] = {"model_type": "unknown"}
        printDebug("")

        newModelsJson = getModelConfigAll() | addModels
        outputFileString = json.dumps(newModelsJson, indent=4)

        printDump("\nNew models.json:\n" + outputFileString)

        deleteFile(CONFIGS_PATH + MODELS_CONFIG_FILE_NAME)
        appendFile(CONFIGS_PATH + MODELS_CONFIG_FILE_NAME, outputFileString)
        loadModelConfiguration()

        printGreen("\nSuccessfully updated your models.json!\n")
    else:
        printError(
            "\nCould not update your models.json "
            "- check your connection?\n"
        )
    return
