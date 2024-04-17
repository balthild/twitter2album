package main

import (
	"fmt"
	"log"
	"net/url"
	"strings"

	"github.com/davecgh/go-spew/spew"
	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	twitterscraper "github.com/n0madic/twitter-scraper"
	"golang.org/x/exp/slices"
)

type AppContext struct {
	config     AppConfig
	bot        *tgbotapi.BotAPI
	scraper    *twitterscraper.Scraper
	noTextMode *UserFlags
}

func (ctx AppContext) run() {
	u := tgbotapi.NewUpdate(0)
	u.Timeout = 60

	updates := ctx.bot.GetUpdatesChan(u)

	log.Println("Listening for bot updates...")

	for update := range updates {
		if update.Message != nil {
			go MessageContext{&ctx, update.Message}.handleMessage(update.Message)
		}
	}
}

type MessageContext struct {
	*AppContext
	message *tgbotapi.Message
}

func (ctx MessageContext) reply(html string) {
	reply := tgbotapi.NewMessage(ctx.message.Chat.ID, html)
	reply.ReplyToMessageID = ctx.message.MessageID
	reply.ParseMode = "HTML"
	reply.DisableWebPagePreview = true
	ctx.bot.Send(reply)
}

func (ctx MessageContext) chatInWhitelist(message *tgbotapi.Message) bool {
	return slices.Contains(ctx.config.TelegramChatWhitelist, message.Chat.ID)
}

func (ctx MessageContext) handleMessage(message *tgbotapi.Message) {
	if !ctx.chatInWhitelist(message) {
		ctx.reply(fmt.Sprintf("User ID: <code>%d</code>", message.From.ID))
		return
	}

	fields := strings.Fields(message.Text)
	if len(fields) == 0 {
		return
	}

	if len(fields) == 1 && fields[0] == "/notext" {
		new := ctx.noTextMode.Toggle(message.From.ID)
		if new {
			ctx.reply("No Text Mode turned on")
		} else {
			ctx.reply("No Text Mode turned off")
		}

		return
	}

	if fields[0] == "/notext" {
		ctx.handleTwitter(fields[1], true)
		return
	}

	if fields[0] == "/relogin" {
		ctx.handleReLogin()
		return
	}

	noTextMode := ctx.noTextMode.Get(message.From.ID)
	ctx.handleTwitter(fields[0], noTextMode)
}

func (ctx MessageContext) handleReLogin() {
	err := loginTwitter(ctx.config, ctx.scraper)
	if err != nil {
		ctx.reply(err.Error())
		return
	}

	ctx.reply("Logged in.")
}

func (ctx MessageContext) handleTwitter(tweetField string, noTextMode bool) {
	tweetUrl, err := url.Parse(tweetField)
	if err != nil {
		ctx.reply("Invalid tweet URL")
		return
	}

	twitterHosts := []string{
		"twitter.com",
		"x.com",
		"vxtwitter.com",
		"fxtwitter.com",
	}
	if !slices.Contains(twitterHosts, tweetUrl.Host) {
		ctx.reply("Invalid tweet URL")
		return
	}

	match := TWEET_URL_PATH.FindStringSubmatch(tweetUrl.Path)
	if len(match) != 2 {
		ctx.reply("Invalid tweet URL")
		return
	}

	tweetId := match[1]
	tweet, err := ctx.scraper.GetTweet(tweetId)
	if err != nil {
		ctx.reply(err.Error())
		return
	}

	if len(tweet.Photos)+len(tweet.Videos)+len(tweet.GIFs) == 0 {
		ctx.reply("The tweet contains no media")
		return
	}

	if ctx.bot.Debug {
		spew.Dump(tweet)
	}

	hasSetCaption := false
	setCaption := func(media *tgbotapi.BaseInputMedia) {
		if !hasSetCaption {
			hasSetCaption = true
			media.ParseMode = "HTML"
			media.Caption = transformTweetText(tweet, noTextMode)
		}
	}

	medias := []interface{}{}
	for _, photo := range tweet.Photos {
		media := tgbotapi.NewInputMediaPhoto(tgbotapi.FileURL(photo.URL))
		setCaption(&media.BaseInputMedia)
		medias = append(medias, media)
	}
	for _, video := range tweet.Videos {
		media := tgbotapi.NewInputMediaVideo(tgbotapi.FileURL(video.URL))
		setCaption(&media.BaseInputMedia)
		medias = append(medias, media)
	}
	for _, gif := range tweet.GIFs {
		media := tgbotapi.NewInputMediaVideo(tgbotapi.FileURL(gif.URL))
		setCaption(&media.BaseInputMedia)
		medias = append(medias, media)
	}

	album := tgbotapi.NewMediaGroup(ctx.message.Chat.ID, medias)
	ctx.bot.Send(album)
}
