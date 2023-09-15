package main

import (
	"log"
	"os"
	"regexp"

	"github.com/davecgh/go-spew/spew"
	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	twitterscraper "github.com/n0madic/twitter-scraper"
	"golang.org/x/exp/slices"
)

var TWEET_URL_PATH = regexp.MustCompile(`^/\w+/status/(\d+)`)

func main() {
	config := loadConfig()

	if slices.Contains(os.Args, "-v") {
		spew.Dump(config)
	}

	bot, err := tgbotapi.NewBotAPI(config.TelegramBotToken)
	if err != nil {
		log.Panic(err)
	}

	scraper := twitterscraper.New()
	loginTwitter(config, scraper)

	noTextMode, err := LoadUserFlags("notext.json")
	if err != nil {
		log.Panic(err)
	}

	ctx := AppContext{
		config:     config,
		bot:        bot,
		scraper:    scraper,
		noTextMode: noTextMode,
	}

	log.Println("Initialization finished.")

	ctx.run()
}
