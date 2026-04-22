from html.parser import HTMLParser

class MyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.line_stack = []

    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            self.stack.append(tag)
            self.line_stack.append(self.getpos()[0])

    def handle_endtag(self, tag):
        if tag == 'div':
            if self.stack:
                self.stack.pop()
                self.line_stack.pop()
            else:
                print(f"Extra closing </div> at line {self.getpos()[0]}")

parser = MyHTMLParser()
with open("templates/compare_prices.html", "r") as f:
    # We should strip jinja to avoid confusing the parser, but let's try raw
    parser.feed(f.read())
print("Unclosed <div>s remaining:", len(self.stack) if hasattr(parser, 'stack') else 'error')
