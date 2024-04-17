package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"regexp"
	"strings"

	twitterscraper "github.com/n0madic/twitter-scraper"
)

func loadTwitterCookies(scraper *twitterscraper.Scraper) error {
	f, err := os.Open("cookies.json")
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}

	var cookies []*http.Cookie
	err = json.NewDecoder(f).Decode(&cookies)
	if err != nil {
		return err
	}

	scraper.SetCookies(cookies)

	return nil
}

func saveTwitterCookies(scraper *twitterscraper.Scraper) error {
	cookies := scraper.GetCookies()

	data, err := json.Marshal(cookies)
	if err != nil {
		return err
	}

	f, err := os.Create("cookies.json")
	if err != nil {
		return err
	}

	_, err = f.Write(data)
	if err != nil {
		return err
	}

	return nil
}

func loginTwitter(config AppConfig, scraper *twitterscraper.Scraper) error {
	err := loadTwitterCookies(scraper)
	if err != nil {
		return err
	}

	if scraper.IsLoggedIn() {
		return nil
	}

	err = scraper.Login(config.TwitterUsername, config.TwitterPassword)
	if err != nil {
		return err
	}

	err = saveTwitterCookies(scraper)
	if err != nil {
		return err
	}

	return nil
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
