package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"regexp"
	"strings"

	twitterscraper "github.com/n0madic/twitter-scraper"
)

func loadTwitterCookies(scraper *twitterscraper.Scraper) {
	f, err := os.Open("cookies.json")
	if os.IsNotExist(err) {
		return
	}
	if err != nil {
		log.Panic(err)
	}

	var cookies []*http.Cookie
	err = json.NewDecoder(f).Decode(&cookies)
	if err != nil {
		log.Panic(err)
	}

	scraper.SetCookies(cookies)
}

func saveTwitterCookies(scraper *twitterscraper.Scraper) {
	cookies := scraper.GetCookies()

	data, err := json.Marshal(cookies)
	if err != nil {
		log.Panic(err)
	}

	f, err := os.Create("cookies.json")
	if err != nil {
		log.Panic(err)
	}

	_, err = f.Write(data)
	if err != nil {
		log.Panic(err)
	}
}

func loginTwitter(config AppConfig, scraper *twitterscraper.Scraper) {
	loadTwitterCookies(scraper)
	if scraper.IsLoggedIn() {
		return
	}

	err := scraper.Login(config.TwitterUsername, config.TwitterPassword)
	if err != nil {
		log.Panic(err)
	}

	saveTwitterCookies(scraper)
}

var TWEET_EMBEDDED_URL = regexp.MustCompile(`https://t\.co/\w+`)

func transformTweetText(tweet *twitterscraper.Tweet, noText bool) string {
	source := fmt.Sprintf(`<a href="%s">source</a>`, tweet.PermanentURL)
	if noText {
		return source
	}

	i := 0
	text := TWEET_EMBEDDED_URL.ReplaceAllStringFunc(tweet.Text, func(s string) string {
		if i >= len(tweet.URLs) {
			return ""
		}
		i += 1

		return tweet.URLs[i-1]
	})

	text = strings.TrimSpace(text)

	return fmt.Sprintf(`%s %s`, text, source)
}
