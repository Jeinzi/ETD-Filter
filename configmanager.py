#!/usr/bin/env python3
import json


def readConfig(configFilePath = "config.json"):
  """Read and parse the config file as a dictionary.

  :return: The config file as a dictionary.
  """

  try:
    with open(configFilePath) as configFile:
      config = json.load(configFile)
  except FileNotFoundError as e:
    errorMessage = "Konfigurationsdatei konnte nicht geöffnet werden. ('{}')"
    errorMessage = errorMessage.format(e.filename)
    print(errorMessage)
    exit()
  except json.decoder.JSONDecodeError:
    errorMessage = "Konfigurationsdatei konnte nicht dekodiert werden. ('{}')"
    errorMessage = errorMessage.format(configFilePath)
    print(errorMessage)
    exit()
  return config
