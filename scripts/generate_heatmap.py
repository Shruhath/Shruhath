#!/usr/bin/env python3
"""Generate a rolling GitHub contribution heatmap using active-day percentile ranks."""
import bisect
import datetime as dt
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
QUERY = '''query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}'''
PALETTES = {
    'dark': (['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353'], '#8b949e', '#30363d'),
    'light': (['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39'], '#57606a', '#d0d7de'),
}


def fetch(login, token):
    req = Request('https://api.github.com/graphql',
                  data=json.dumps({'query': QUERY, 'variables': {'login': login}}).encode(),
                  headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
                           'User-Agent': 'percentile-contribution-heatmap'})
    with urlopen(req, timeout=30) as response:
        payload = json.load(response)
    if payload.get('errors'):
        raise RuntimeError(str(payload['errors']))
    user = payload['data']['user']
    if user is None:
        raise RuntimeError('GitHub user not found')
    weeks = user['contributionsCollection']['contributionCalendar']['weeks']
    days = {dt.date.fromisoformat(d['date']): int(d['contributionCount'])
            for w in weeks for d in w['contributionDays']}
    if not days:
        raise RuntimeError('GitHub returned no calendar dates')
    return days


def level(count, active):
    if count == 0:
        return 0
    # Upper percentile rank: identical counts always have identical colours.
    # Zero-contribution days do not distort the distribution of active days.
    rank = bisect.bisect_right(active, count)
    return max(1, min(4, (4 * rank + len(active) - 1) // len(active)))


def render(days, theme):
    colors, muted, stroke = PALETTES[theme]
    active = sorted(n for n in days.values() if n > 0)
    first, last = min(days), max(days)
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)
    cols = (last - start).days // 7 + 1
    width = max(300, 37 + cols * 13)
    total = sum(days.values())
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 141" width="{width}" height="141" role="img" aria-label="{total} GitHub contributions; percentile heatmap">',
           f'<title>{total:,} contributions · {first} to {last}</title>',
           f'<g font-family="Arial, Helvetica, sans-serif" font-size="10" fill="{muted}">']
    for row, label in [(1, 'Mon'), (3, 'Wed'), (5, 'Fri')]:
        out.append(f'<text x="0" y="{25+row*13+8}">{label}</text>')
    last_label = -4
    for day in sorted(days):
        col = (day-start).days//7
        if (day == first or day.day == 1) and col-last_label >= 3:
            out.append(f'<text x="{30+col*13}" y="15">{day.strftime("%b")}</text>')
            last_label = col
    out.append(f'<text x="30" y="133">{total:,} contributions</text>')
    lx = width - 123
    out.append(f'<text x="{lx-25}" y="133">Less</text>')
    for i, color in enumerate(colors):
        out.append(f'<rect x="{lx+i*13}" y="124" width="10" height="10" rx="2" fill="{color}"/>')
    out.append(f'<text x="{lx+68}" y="133">More</text></g>')
    for day, count in sorted(days.items()):
        col, row = divmod((day-start).days, 7)
        color = colors[level(count, active)]
        out.append(f'<rect x="{30+col*13}" y="{25+row*13}" width="10" height="10" rx="2" fill="{color}" stroke="{stroke}" stroke-opacity="0.25"><title>{count} contributions on {escape(day.isoformat())}</title></rect>')
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def main():
    token = os.environ.get('GH_TOKEN')
    if not token:
        raise SystemExit('Set GH_TOKEN to a GitHub token before running.')
    days = fetch(os.environ.get('GH_LOGIN', 'Shruhath'), token)
    assets = ROOT / 'assets'
    assets.mkdir(exist_ok=True)
    for theme, filename in [('dark', 'contributions.svg'), ('light', 'contributions-light.svg')]:
        (assets / filename).write_text(render(days, theme), encoding='utf-8')
    print(f'Generated both heatmaps for {len(days)} days; {sum(days.values())} contributions.')


if __name__ == '__main__':
    main()
