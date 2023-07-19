package main

import (
	"log"
	"regexp"

	"github.com/davecgh/go-spew/spew"
	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	twitterscraper "github.com/n0madic/twitter-scraper"
)

var TWEET_URL_PATH = regexp.MustCompile(`^/\w+/status/(\d+)`)

func main() {
	config := loadConfig()
	spew.Dump(config)

	bot, err := tgbotapi.NewBotAPI(config.TelegramBotToken)
	if err != nil {
		log.Panic(err)
	}

	scraper := twitterscraper.New()
	loginTwitter(config, scraper)

	ctx := AppContext{
		config:  config,
		bot:     bot,
		scraper: scraper,
	}

	ctx.run()
}
