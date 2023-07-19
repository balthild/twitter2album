package main

import (
	"log"
	"os"

	"github.com/pelletier/go-toml/v2"
)

type AppConfig struct {
	TelegramBotToken      string
	TelegramChatWhitelist []int64
	TwitterUsername       string
	TwitterPassword       string
}

func loadConfig() AppConfig {
	f, err := os.Open("config.toml")
	if err != nil {
		log.Panic(err)
	}

	var config AppConfig
	err = toml.NewDecoder(f).Decode(&config)
	if err != nil {
		log.Panic(err)
	}

	return config
}
