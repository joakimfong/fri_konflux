#! /usr/bin/python3
# -*- coding: utf-8 -*-

import getopt
import json
import markdown
import os
import sys

from html.parser import HTMLParser
from html.entities import name2codepoint

SIDHUVUD = '''
<!DOCTYPE html">
<head>
<meta charset="utf-8">
<style> @import "{}style.css"</style>
</head>

<div id="nav" class="nav"></div>
<script async type="text/javascript" src="{}nav_data.js"></script>
<script async type="text/javascript" src="{}nav.js"></script>
<div class="content">

'''

def ladda_biblio(biblio):
    with open(biblio, encoding='utf-8') as f:
        return json.load(f)

def alla_md_filer(sökväg):
    return sorted([f for f in os.listdir(sökväg) if f.endswith('.md')])

def alla_html_filer(sökväg):
    return sorted([f for f in os.listdir(sökväg) if f.endswith('.html')])

class Referens(object):
    tag = None
    idn = None
    txt = None
    
    def __init__(self, tag, idn):
        self.tag = tag
        self.idn = idn
        self.txt = ''

    def dict(self):
        return {
            "tag"  : self.tag,
            "id"   : self.idn,
            "text" : self.txt
        }

class Referator(HTMLParser):
    refs = None
    curr = None

    def __init__(self):
        HTMLParser.__init__(self)
        self.refs = []
        
    def handle_starttag(self, tag, attrs):
        if tag in ['h1', 'h2', 'h3']:
            idn = None
            for a in attrs:
                if a[0] == 'id':
                    idn = a[1]
            if idn != None:
                self.curr = Referens(tag, idn)

    def handle_endtag(self, tag):
        if self.curr != None and self.curr.tag == tag:
            self.refs.append(self.curr)
            self.curr = None

    def handle_data(self, data):
        if self.curr != None:
            self.curr.txt += data

    def handle_entityref(self, name):
        if self.curr != None:
            self.curr.txt += chr(name2codepoint[name])

class LänkLus(HTMLParser):
    html_sökväg = None
    md_sökväg   = None
    
    def __init__(self, html_sökväg, md_sökväg):
        HTMLParser.__init__(self)
        self.html_sökväg = html_sökväg
        self.md_sökväg   = md_sökväg

    def handle_starttag(self, tag, attrs):
        if tag != 'a': # vi bryr oss bara om <a href>
            return

        href = None
        for a in attrs:
            if a[0] == 'href':
                href = a[1]

        # vi bryr oss inte om tomma <a>-element eller sådana som leder till andra domäner,
        # e-postadresser, absoluta filsökvägar eller ankare som inte hör till en sökväg.
        if href == None:
            return
        if href.startswith('http:'):
            return
        if href.startswith('https:'):
            return
        if href.startswith('mailto:'):
            return
        if href.startswith('/'):
            return
        if href.startswith('#'): #fixme
            return

        split = href.split('#', 1)
        sökväg = split[0]
        ankare = split[1] if len(split) > 1 else None
        länk = os.path.realpath(os.path.join(os.path.dirname(self.html_sökväg), sökväg))

        if not os.path.isfile(länk):
            print(self.md_sökväg + ': refererad fil finns inte: ' + href)
            return
        if ankare:
            # leta efter strängen 'id="<ankare>"' i den länkade filen. markdown skapar
            # alltid länkar på det formatet så vi behöver inte bry oss om alla andra
            # varianter som html stödjer.
            with open(länk, encoding='utf-8') as f:
                if 'id="' + ankare + '"' not in f.read():
                    print(self.md_sökväg + ': refererat ankare finns inte i filen: ' + href)
                    return

class Sida(object):
    md_sökväg   = None
    nivå        = 0
    html_sökväg = None
    referenser  = None
    
    def __init__(self, md_sökväg, nivå):
        self.md_sökväg = md_sökväg
        self.nivå      = nivå

    def bygg(self):
        huvud = SIDHUVUD.format('../' * self.nivå, '../' * self.nivå, '../' * self.nivå)
        with open(self.md_sökväg, encoding='utf-8-sig') as f:
            kropp = markdown.markdown(f.read(), extensions=['extra', 'toc'])
        fot  = '</div></div>'
        html = huvud + kropp + fot

        s,e = os.path.splitext(self.md_sökväg)
        self.html_sökväg = s + '.html'

        with open(self.html_sökväg, 'w', encoding='utf-8') as f:
            f.write(html)

        r = Referator()
        r.feed(html)
        self.referenser = r.refs

    def länklusning(self):
        lus = LänkLus(self.html_sökväg, self.md_sökväg)
        with open(self.html_sökväg, encoding='utf-8') as f:
            lus.feed(f.read())

    def dict(self):
        return {
            'path': os.path.basename(self.html_sökväg),
            'refs': [ r.dict() for r in self.referenser ]
        }

class Bok(object):
    sökväg = None
    titel  = None
    sidor  = None
    nivå   = 0
    
    def __init__(self, sökväg, titel, nivå):
        self.sökväg = sökväg
        self.sidor  = []
        self.titel  = titel
        self.nivå   = nivå

    def städa(self):
        html_filer = alla_html_filer(self.sökväg)
    
        for f in html_filer:
            p = os.path.realpath(os.path.join(self.sökväg, f))
            print('-', p)
            os.unlink(p)

    def bygg(self):
        md_filer = alla_md_filer(self.sökväg)

        for f in md_filer:
            p = os.path.realpath(os.path.join(self.sökväg, f))
            print('+', p)
            sida = Sida(p, self.nivå)
            sida.bygg()
            self.sidor.append(sida)

    def länklusning(self):
        for sida in self.sidor:
            sida.länklusning()

    def dict(self):
        tree = '.' if self.nivå == 0 else os.path.basename(self.sökväg)
        return {
            'tree' : tree,
            'title': self.titel,
            'pages': [ s.dict() for s in self.sidor ]
        }

class Nav(object):
    böcker = None

    def __init__(self):
        self.böcker = []

    def ny_bok(self, bok):
        self.böcker.append(bok)

    def länklusning(self):
        for bok in self.böcker:
            bok.länklusning()

    def list(self):
        return [ b.dict() for b in self.böcker ]

    def javascript(self):
        return 'nav_data = ' + json.dumps(self.list(), indent = 2, sort_keys = True) + ';\n'

def bygg(biblio):
    if not os.path.exists(biblio):
        print('hittar inte filen:', biblio)
        return
    
    böcker = ladda_biblio(biblio)
    rot    = os.path.dirname(os.path.realpath(__file__))
    nav    = Nav()

    for katalog, titel in böcker:
        sökväg = os.path.join(rot, katalog)
        bok = Bok(sökväg, titel, 0 if katalog == '.' else 1)
        bok.städa()
        bok.bygg()
        nav.ny_bok(bok)

    nav.länklusning()

    with open(os.path.join(rot, 'nav_data.js'), 'w', encoding='utf-8') as f:
        f.write(nav.javascript())

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('du måste ange en fil med böcker')
        sys.exit(1)
    biblio = sys.argv[1]
    bygg(biblio)
