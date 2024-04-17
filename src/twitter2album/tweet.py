import re
from twscrape import Tweet

def render_content(tweet: Tweet, notext: bool) -> str:
    source = f'<a href="{tweet.url}">source</a>'
    if notext:
        return source

    content = tweet.rawContent
    for link in tweet.links:
        content = content.replace(link.tcourl, f'<a href="{link.url}">{link.text}</a>')

    content = re.sub('https://t\.co/\w+', '', content).strip()

    sep = '\n' if '\n' in content else ' '
    return f'{content}{sep}{source}'.strip()
