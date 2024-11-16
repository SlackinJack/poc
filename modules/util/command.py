import json
import os


from modules.file.operation import readFile, deleteFile
from modules.util.configuration import setConfigurationFileName
from modules.util.configuration import getConfigurationFileName
from modules.util.configuration import loadConfiguration, setDefaultTextModel
from modules.util.configuration import loadModelConfiguration
from modules.util.configuration import setConfig, getConfig
from modules.util.conversation import getConversationName, setConversation
from modules.util.model import getModelFromConfiguration
from modules.util.model import getModelByNameAndType, getModelsWithType
from modules.util.model import modelScanner, getModelTypes
from modules.util.response import getTextToTextResponseStreamed
from modules.util.strings.paths import CONFIGS_PATH, CONVERSATIONS_FILE_PATH
from modules.util.strings.endpoints import MODELS_APPLY_ENDPOINT
from modules.util.strings.endpoints import MODELS_AVAILABLE_ENDPOINT
from modules.util.strings.endpoints import MODELS_ENDPOINT
from modules.util.trigger import checkTriggers
from modules.util.util import printGeneric, printMenu, getStringMatchPercentage
from modules.util.util import printError, printSeparator, clearWindow
from modules.util.util import printSetting, printGreen, printRed, printDebug
from modules.util.util import printCurrentSystemPrompt, checkEmptyString
from modules.util.util import printInput, sendCurlCommand
from modules.util.util import setOrPresetValue
from modules.util.util import getRandomSeed, intVerifier, startTimer, endTimer


def getCommandMap():
    return {
        commandHelp:            ["/help",           "General",      "Shows all available commands."],
        commandClear:           ["/clear",          "General",      "Clears the prompt window."],
        commandConfig:          ["/config",         "General",      "Reload the configuration files."],
        commandSettings:        ["/settings",       "General",      "Prints all current settings."],
        commandExit:            ["/exit",           "General",      "Exits the program."],

        commandConvo:           ["/convo",          "Settings",     "Change the conversation file."],
        commandModel:           ["/model",          "Settings",     "Change models."],
        commandSystemPrompt:    ["/system",         "Settings",     "Change the system prompt."],


        commandCurl:            ["/curl",           "Tools",        "Send cURL commands to the server."],
        commandModelScanner:    ["/modelscanner",   "Tools",        "Scan for models on the server."]
    }


# General Commands


def commandHelp():
    printGeneric("\nAvailable commands:")
    currentCategory = ""
    for c in getCommandMap().values():
        commandName = c[0]
        commandCategory = c[1]
        commandDescription = c[2]
        if len(currentCategory) == 0:
            currentCategory = commandCategory
            printGeneric(
                "\n--------------------"
                " " + currentCategory + " "
                "--------------------\n"
            )
        else:
            if not currentCategory == commandCategory:
                currentCategory = commandCategory
                printGeneric(
                    "\n--------------------"
                    " " + currentCategory + " "
                    "--------------------\n"
                )
        printGeneric(" - " + commandName + " > " + commandDescription)
    printGeneric("")
    return


def commandClear():
    clearWindow()
    return


def commandConfig():
    choices = [
        "Load",
        "Reload"
    ]

    def menu():
        selection = printMenu("Configuration menu", "", choices)
        if selection is None:
            return
        elif selection == "Load":
            submenuConfigLoad()
        elif selection == "Reload":
            submenuConfigReload()
        else:
            printError("\nInvalid selection.\n")
        printSeparator()
        menu()
        return
    menu()
    printGeneric("\nReturning to main menu.\n")
    return


def submenuConfigLoad():
    configList = []

    for config in os.listdir(CONFIGS_PATH):
        if config != "models.json" and config.endswith(".json"):
            configList.append(config)

    choices = configList

    def config_verifier(configNameIn):
        if len(configNameIn) > 0:
            bestMatch = None
            configNameIn = configNameIn.lower()
            for config in configList:
                if configNameIn.lower() == config.lower():
                    return [config, True]
                elif configNameIn in config.lower():
                    if bestMatch is not None:
                        if getStringMatchPercentage(
                            configNameIn,
                            config.lower()
                        ) > (
                            getStringMatchPercentage(
                                bestMatch.lower(),
                                config.lower()
                            )
                        ):
                            bestMatch = config
                    else:
                        bestMatch = config
            if bestMatch is not None:
                return [bestMatch, True]
        return ["", False]

    selection = printMenu("Configurations available", "", choices)
    if selection is not None:
        if len(selection) > 0:
            nextConfiguration = config_verifier(selection)
            if nextConfiguration[1]:
                setConfigurationFileName(nextConfiguration[0])
                printGreen(
                    "\nConfiguration set to " + nextConfiguration[0] + "\n"
                )
                loadModelConfig()
                loadConfig()
            else:
                printError(
                    "\nCannot find configuration - "
                    "returning to configuration menu.\n"
                )
        else:
            printError(
                "\nInvalid selection - returning to configuration menu.\n"
            )
    else:
        printRed("\nReturning to configuration menu.\n")
    return


def submenuConfigReload():
    loadModelConfig()
    loadConfig()
    printGreen("\nConfiguration reloaded.\n")
    return


def commandSettings():
    printGeneric("\nConfiguration File:")
    printGeneric(getConfigurationFileName())

    printGeneric("\nModels:")
    for modelType, modelName in getModelTypes().items():
        printGeneric(
            modelName + ": " + str(
                getConfig("default_" + modelType + "_model")
            )
        )

    printGeneric("\nConversation file: " + getConversationName() + ".convo")

    printGeneric("\nSystem prompt:")
    printCurrentSystemPrompt(getConfig("system_prompt"), printGeneric, "")

    printGeneric("")
    return


def commandExit():
    for conversation in os.listdir(CONVERSATIONS_FILE_PATH):
        if conversation.endswith(".convo"):
            if checkEmptyString(
                readFile(
                    CONVERSATIONS_FILE_PATH + conversation,
                    None
                )
            ):
                deleteFile(CONVERSATIONS_FILE_PATH + conversation)
                printDebug(
                    "\nDeleted empty conversation file: " + conversation
                )

    printGeneric("")
    return


# Settings Commands


def commandConvo():
    convoList = []

    for conversation in os.listdir(CONVERSATIONS_FILE_PATH):
        if conversation.endswith(".convo"):
            convoName = conversation.replace(".convo", "")
            convoList.append(convoName)

    choices = convoList

    def convo_verifier(convoNameIn):
        if len(convoNameIn) > 0:
            for conversation in convoList:
                if convoNameIn in conversation:
                    return conversation
        return convoNameIn

    selection = printMenu("Conversations available", "", choices)
    if selection is not None:
        if len(selection) > 0:
            conversationName = convo_verifier(selection)
            setConversation(conversationName)
            printGreen("\nConversation set to: " + conversationName + "\n")
        else:
            printError("\nInvalid selection - returning to menu.\n")
    else:
        printRed(
            "\nKeeping current conversation"
            ": " + getConversationName() + "\n"
        )
    return


def commandSystemPrompt():
    printGeneric("\nCurrent system prompt:")
    printCurrentSystemPrompt(getConfig("system_prompt"), printGeneric, "\n")
    printSeparator()
    setConfig("system_prompt", printInput("Enter the new system prompt"))
    printSeparator()
    printGreen("\nSet system prompt to:")
    printCurrentSystemPrompt(getConfig("system_prompt"), printGreen, "\n")
    return


def commandModel():
    choices = list(getModelTypes().values())

    def menu():
        selection = printMenu(
            "Model menu",
            "(Tip: You can use spaces to match for long model names!)",
            choices
        )
        matched = False
        if selection is None:
            return
        else:
            for k, v in getModelTypes().items():
                if selection == v:
                    matched = True
                    modelChanger(k, v)
                    break
            if not matched:
                printError("\nInvalid selection.\n")
        printSeparator()
        menu()
        return
    menu()
    printGeneric("\nReturning to main menu.\n")
    return


def model_verifier(nextModelIn, modelTypeIn):
    result = getModelByNameAndType(
        nextModelIn,
        modelTypeIn,
        True, False,
        False
    )
    return [result, (result is not None)]


def modelChanger(modelTypeIn, modelTypeNameIn):
    choices = list(getModelsWithType(modelTypeIn))
    selection = printMenu("Available models", "", choices)
    if selection is not None:
        if len(selection) > 0:
            matched = model_verifier(selection, modelTypeIn)
            if matched[1]:
                setConfig("default_" + modelTypeIn + "_model", matched[0])
                printGreen(
                    "\n" + modelTypeNameIn + " model set to"
                    ": " + matched[0] + "\n"
                )
            else:
                printError(
                    "\nCannot find a match - "
                    "keeping current " + modelTypeNameIn + " model"
                    ": " + getConfig(
                        "default_" + modelTypeIn + "_model"
                    ) + "\n"
                )
        else:
            printRed("\nInvalid selection - returning to models menu.\n")
    else:
        printRed(
            "\nKeeping current model"
            ": " + getConfig("default_" + modelTypeIn + "_model") + "\n"
        )
    return


# Tools Commands


def commandCurl():
    choices = [
        "Apply",
        "Available",
        "Models",
        "Raw"
    ]

    def menu():
        selection = printMenu("cURL menu", "", choices)
        if selection is None:
            return
        elif selection == "Apply":
            sendCurlCommand(MODELS_APPLY_ENDPOINT)
        elif selection == "Available":
            sendCurlCommand(MODELS_AVAILABLE_ENDPOINT)
        elif selection == "Models":
            sendCurlCommand(MODELS_ENDPOINT)
        elif selection == "Raw":
            submenuCurlRaw()
        else:
            printError("\nInvalid selection.\n")
        printSeparator()
        menu()
        return
    menu()
    printGeneric("\nReturning to main menu.\n")
    return


def submenuCurlRaw():
    dest = printInput("Enter the endpoint (eg. v1/chat/completions)")
    printSeparator()
    jsonData = "{" + printInput("Input the JSON data") + "}"
    printSeparator()
    sendCurlCommand(dest, dataIn=json.loads(jsonData))
    return


def commandModelScanner():
    modelScanner()
    return


def loadModelConfig():
    loadModelConfiguration()
    return


def loadConfig():
    loadConfiguration()

    for modelType in list(getModelTypes()):
        setConfig(
            "default_" + modelType + "_model",
            getModelFromConfiguration(
                getConfig("default_" + modelType + "_model"),
                modelType,
                False
            )
        )

    setDefaultTextModel(getConfig("default_text_to_text_model"))
    return


def handlePrompt(promptIn):
    if not checkCommands(promptIn):
        seed = getRandomSeed()
        if not checkTriggers(promptIn, seed, getTextToTextResponseStreamed):
            startTimer(0)
            getTextToTextResponseStreamed(promptIn, seed)
            endTimer(0)
    return


def checkCommands(promptIn):
    if promptIn.startswith("/"):
        for func, value in getCommandMap().items():
            if promptIn == value[0]:
                func()
                return True
        printError("\nUnknown command.\n")
        return True
    else:
        printDebug("\nNo commands detected.")
    return False
