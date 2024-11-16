from pynput import keyboard


from modules.util.command import loadModelConfig, loadConfig, handlePrompt
from modules.util.command import commandExit, commandHelp, commandSettings
from modules.util.conversation import setConversation, getConversationName
from modules.util.util import printInput, printGeneric
from modules.util.util import printSeparator, clearWindow, checkEmptyString


###########################
""" BEGIN INITALIZATION """
###########################


clearWindow()

loadModelConfig()
loadConfig()


setConversation(getConversationName())

printSeparator()

commandSettings()


##################
""" BEGIN MAIN """
##################


def main():
    printSeparator()
    prompt = printInput("Enter a prompt (\"/help\" for list of commands)")
    printSeparator()
    if not checkEmptyString(prompt):
        if prompt == "exit" or prompt == "0" or prompt.startswith("/exit"):
            commandExit()
            return
        else:
            handlePrompt(prompt)
    else:
        commandHelp()
    main()


main()
