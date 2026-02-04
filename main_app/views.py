import logging
import math
import random

from django.http import FileResponse, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from main_app.models import Article, Newspaper, create_frequency_csv
from main_app.types import SearchResult
from main_app.utils import (
    aggregate_word_stats,
    article_stats,
    filter_by_match_type,
    frequency_stats,
)

logger = logging.getLogger(__name__)

# from main_app.utils import frequency_stats as f


# index view
def index(request):
    """
    Index view for main page
    """
    context = {
        "newspapers": Newspaper.objects.prefetch_related("article_set"),
        "word_frequency": frequency_stats(Article.objects.all()),
        "article_count": Article.objects.count(),
        "word_count": Article.objects.count() * 500,
        "text_stats": article_stats(Article.objects.all()),
        "name_counts": Article.objects.total_name_counts(),
        "published_years": Article.objects.values("published_year")
        .distinct()
        .order_by("published_year")
        .values_list("published_year", flat=True),
        # "unique_word_count": Article.objects.unique_word_count(),
    }
    return render(request, "index.html", context)


# search view
def search(request: HttpRequest):
    """
    Search view for searching articles
    """
    # get search query
    query = request.GET.get("q")
    language = int(request.GET.get("language"))
    year = request.GET.get("year") or None
    match_type = int(request.GET.get("match_type") or 0)
    print(f"match_type: {match_type}")
    # get search results
    results: SearchResult = Article.objects.search(query, language, year)
    if match_type != 0:
        results = filter_by_match_type(results, match_type)
    # render search results
    return render(
        request, "search.html", {"results": results, "match_type": match_type}
    )


def search_new(request: HttpRequest):
    """Experimental search view with yearly chart and grouped results."""

    query = (request.GET.get("q") or "").strip()
    language = int(request.GET.get("language") or Article.ENGLISH)
    year = request.GET.get("year") or None
    match_type = int(request.GET.get("match_type") or 0)

    results: SearchResult = Article.objects.search(query, language, year)
    if match_type != 0:
        results = filter_by_match_type(results, match_type)

    grouped: dict[int, dict] = {}
    for item in results["results"]:
        article = item["article"]
        year_val = article.published_year or 0

        bucket = grouped.setdefault(
            year_val, {"year": year_val, "total_frequency": 0, "articles": {}}
        )
        bucket["total_frequency"] += item["frequency"]

        articles_map = bucket["articles"]
        art = articles_map.setdefault(
            article.id,
            {"article_id": article.id, "title": article.title, "matches": []},
        )

        for loc in item["locations"]:
            art["matches"].append({"type": loc["type"], "context": loc["context"]})

    year_sections = sorted(grouped.values(), key=lambda x: x["year"], reverse=True)
    for bucket in year_sections:
        bucket["articles"] = list(bucket["articles"].values())

    year_chart = [
        {"year": bucket["year"], "total": bucket["total_frequency"]}
        for bucket in sorted(grouped.values(), key=lambda x: x["year"])
        if bucket["year"] != 0
    ]

    return render(
        request,
        "search_new.html",
        {
            "query": query,
            "results": results,
            "match_type": match_type,
            "year_sections": year_sections,
            "year_chart": year_chart,
        },
    )


def article_detail(request, article_id):
    """
    Article detail view
    """
    # get article
    article = Article.objects.get(id=article_id)
    word_stats = aggregate_word_stats([article])
    name_stats = Article.objects.annotated_name_stats(
        Article.objects.filter(id=article_id)
    )
    # render article detail
    return render(
        request,
        "article_detail.html",
        {
            "article": article,
            "word_frequency": word_stats["frequency"],
            "word_count": word_stats["total_words"],
            "text_stats": word_stats,
            "name_stats": name_stats,
        },
    )


def word_frequency_data(request: HttpRequest) -> JsonResponse | HttpResponse:
    """
    return json object of word frequency data plus annotated name stats
    """

    def resolve_language():
        return (
            Article.UZBEK if request.GET.get("language") == "uzbek" else Article.ENGLISH
        )

    def resolve_language_label():
        return "uzbek" if request.GET.get("language") == "uzbek" else "english"

    def build_names_csv(articles, filename: str) -> HttpResponse:
        import csv

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow(["name", "gender", "count"])
        name_stats = Article.objects.annotated_name_stats(articles)
        for item in name_stats["frequency"]:
            writer.writerow([item["name"], item["gender"], item["count"]])
        return response

    # check if "full" parameter is passed
    if request.GET.get("full"):
        language_code = resolve_language()
        language_label = resolve_language_label()
        dataset = request.GET.get("dataset") or "words"
        articles = Article.objects.filter(language=language_code)

        if dataset == "names":
            filename = f"annotated_names_{language_label}.csv"
            return build_names_csv(articles, filename)

        filename = f"word_frequency_{language_label}.csv"
        return create_frequency_csv(articles, filename)

    else:

        def build_payload(language_code):
            articles = Article.objects.filter(language=language_code)
            word_stats = aggregate_word_stats(articles)
            name_stats = Article.objects.annotated_name_stats(articles)
            return {
                "words": word_stats["frequency"][:20],
                "names": {
                    "frequency": name_stats["frequency"][:20],
                    "counts": name_stats["counts"],
                },
            }

        return JsonResponse(
            {
                "english": build_payload(Article.ENGLISH),
                "uzbek": build_payload(Article.UZBEK),
            },
            safe=False,
        )

    # return JsonResponse(frequency_stats(Article.objects.all())[:20], safe=False)


def article_frequency(request, article_id) -> JsonResponse:
    """
    return json object of word frequency data
    """
    article = Article.objects.get(id=article_id)
    word_stats = aggregate_word_stats([article])
    name_stats = Article.objects.annotated_name_stats(
        Article.objects.filter(id=article_id)
    )
    return JsonResponse(
        {
            "words": word_stats["frequency"][:20],
            "names": {
                "frequency": name_stats["frequency"][:20],
                "counts": name_stats["counts"],
            },
        },
        safe=False,
    )


def handle_csv_upload_view(request: HttpRequest):
    """
    Handle csv upload view
    """
    if request.method == "POST":
        # get csv file from request
        csv_file = request.FILES["file"]
        # print(csv_file)
        # print(dir(csv_file))
        # create article
        # Article.objects.create_from_csv(csv_file.read().decode("utf-8").splitlines())
        Article.objects.create_from_csv(csv_file)
    return render(request, "upload.html", {"newspapers": Newspaper.objects.all()})


def year_archive(request, year: int):
    """
    Year archive view
    """
    # get articles
    # articles = Article.objects.filter(published_year=f"{year}-01-01")

    # get english and uzbek articles separately

    english = Article.objects.filter(language=Article.ENGLISH, published_year=year)
    uzbek = Article.objects.filter(language=Article.UZBEK, published_year=year)

    english_stats = aggregate_word_stats(english)
    uzbek_stats = aggregate_word_stats(uzbek)

    # render year archive
    return render(
        request,
        "year_archive.html",
        {
            "english_article_count": english.count(),
            "english_frequency": english_stats["frequency"],
            "total_english_words": english_stats["total_words"],
            "english_text_stats": english_stats,
            "english_name_stats": Article.objects.annotated_name_stats(english),
            "uzbek_article_count": uzbek.count(),
            "uzbek_frequency": uzbek_stats["frequency"],
            "total_uzbek_words": uzbek_stats["total_words"],
            "uzbek_text_stats": uzbek_stats,
            "uzbek_name_stats": Article.objects.annotated_name_stats(uzbek),
            "year": year,
        },
    )


def year_archive_download(request, year: int, language: str):
    """
    Year archive view
    """
    # get articles
    articles = Article.objects.filter(published_year=year, language=language)
    csv_response = create_frequency_csv(articles, f"{year}_{language}_archieve.csv")

    # render year archive
    return csv_response


def newspaper_detail(request, newspaper_id):
    """
    Newspaper detail view
    """
    # get newspaper
    newspaper = Newspaper.objects.get(id=newspaper_id)
    articles_qs = newspaper.article_set.all()
    name_stats = Article.objects.annotated_name_stats(articles_qs)
    word_stats = aggregate_word_stats(articles_qs)
    # render newspaper detail
    return render(
        request,
        "newspaper_detail.html",
        {
            "newspaper": newspaper,
            "article_count": articles_qs.count(),
            "word_count": word_stats["total_words"],
            "word_frequency": word_stats["frequency"],
            "name_stats": name_stats,
            "text_stats": word_stats,
        },
    )


def newspaper_frequency(request, newspaper_id) -> JsonResponse:
    """
    return json object of word frequency data
    """
    articles = Article.objects.filter(newspaper_id=newspaper_id)
    word_stats = aggregate_word_stats(articles)
    name_stats = Article.objects.annotated_name_stats(articles)

    return JsonResponse(
        {
            "words": word_stats["frequency"][:20],
            "names": {
                "frequency": name_stats["frequency"][:20],
                "counts": name_stats["counts"],
            },
        },
        safe=False,
    )


def author(request):
    """
    Author view that returns pdf file
    """
    response = FileResponse(open("author.pdf", "rb"), content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=NozimjonAtaboyevCV.pdf"
    return response


def geo_placeholder_svg(request, seed: int) -> HttpResponse:
    """Return a dynamically generated geometric SVG placeholder."""

    try:
        rng = random.Random(seed)
        width = 1200
        height = 640

        background_a = "#F8FAFC"
        background_b = "#EEF2FF"
        accents = [
            "#2563EB",
            "#7C3AED",
            "#06B6D4",
            "#10B981",
            "#F59E0B",
            "#F97316",
            "#EF4444",
            "#22C55E",
        ]
        accent_a = rng.choice(accents)
        accent_b = rng.choice([c for c in accents if c != accent_a])
        accent_c = rng.choice([c for c in accents if c not in [accent_a, accent_b]])

        def rand_rect():
            x = rng.randint(60, width - 400)
            y = rng.randint(60, height - 280)
            w = rng.randint(140, 420)
            h = rng.randint(100, 260)
            r = rng.randint(8, 48)
            fill = rng.choice(["#FFFFFF", "#F8FAFC", "#E2E8F0"])
            stroke = rng.choice(["#E2E8F0", "#CBD5E1", "none"])
            stroke_width = rng.randint(1, 3) if stroke != "none" else 0
            rotation = rng.randint(-15, 15)
            cx, cy = x + w / 2, y + h / 2
            return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" transform="rotate({rotation} {cx} {cy})" />'

        def rand_circle():
            cx = rng.randint(120, width - 120)
            cy = rng.randint(120, height - 120)
            r = rng.randint(50, 180)
            fill = rng.choice(["#FFFFFF", "#F8FAFC", "#E2E8F0"])
            stroke = (
                rng.choice(["#E2E8F0", "#CBD5E1", "none"])
                if rng.random() > 0.6
                else "none"
            )
            stroke_width = rng.randint(1, 4) if stroke != "none" else 0
            return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" />'

        def rand_ellipse():
            cx = rng.randint(120, width - 120)
            cy = rng.randint(120, height - 120)
            rx = rng.randint(80, 200)
            ry = rng.randint(40, 120)
            rotation = rng.randint(0, 180)
            fill = rng.choice(["#FFFFFF", "#F8FAFC", "#E2E8F0"])
            return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" transform="rotate({rotation} {cx} {cy})" />'

        def rand_polygon():
            cx = rng.randint(200, width - 200)
            cy = rng.randint(120, height - 120)
            sides = rng.choice([3, 4, 5, 6, 8])
            size = rng.randint(80, 200)
            points = []
            for i in range(sides):
                angle = (i * 360 / sides + rng.randint(-8, 8)) * math.pi / 180
                radius = size * rng.uniform(0.85, 1.15)
                px = int(cx + radius * math.cos(angle))
                py = int(cy + radius * math.sin(angle))
                points.append(f"{px},{py}")
            fill = rng.choice(["#FFFFFF", "#F8FAFC", "#E2E8F0"])
            stroke = (
                rng.choice(["#E2E8F0", "#CBD5E1", "none"])
                if rng.random() > 0.5
                else "none"
            )
            stroke_width = rng.randint(1, 3) if stroke != "none" else 0
            return f'<polygon points="{" ".join(points)}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" />'

        def rand_star():
            cx = rng.randint(200, width - 200)
            cy = rng.randint(120, height - 120)
            outer_r = rng.randint(80, 150)
            inner_r = rng.randint(40, 80)
            points_count = rng.choice([5, 6, 7, 8])
            points = []
            for i in range(points_count * 2):
                angle = (i * 180 / points_count) * math.pi / 180
                radius = outer_r if i % 2 == 0 else inner_r
                px = int(cx + radius * math.cos(angle - math.pi / 2))
                py = int(cy + radius * math.sin(angle - math.pi / 2))
                points.append(f"{px},{py}")
            fill = rng.choice(["#FFFFFF", "#F8FAFC", "#E2E8F0"])
            return f'<polygon points="{" ".join(points)}" fill="{fill}" />'

        def rand_triangle():
            x1 = rng.randint(100, width - 100)
            y1 = rng.randint(80, height - 80)
            x2 = x1 + rng.randint(-150, 150)
            y2 = y1 + rng.randint(120, 250)
            x3 = x1 + rng.randint(-150, 150)
            y3 = y1 + rng.randint(120, 250)
            fill = rng.choice(["#FFFFFF", "#F8FAFC", "#E2E8F0"])
            stroke = rng.choice(["#E2E8F0", "none"]) if rng.random() > 0.6 else "none"
            stroke_width = 2 if stroke != "none" else 0
            return f'<polygon points="{x1},{y1} {x2},{y2} {x3},{y3}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" />'

        def rand_bubble():
            cx = rng.randint(100, width - 100)
            cy = rng.randint(100, height - 100)
            r = rng.randint(30, 120)
            # Use timestamp + random to ensure unique IDs
            gradient_id = f"bubble_{seed}_{cx}_{cy}_{rng.randint(1000, 9999)}"
            bubble_accent = rng.choice([accent_a, accent_b, accent_c])
            opacity = rng.uniform(0.15, 0.35)

            gradient_def = f'''<radialGradient id="{gradient_id}" cx="0.3" cy="0.3" r="0.8">
                <stop offset="0" stop-color="{bubble_accent}" stop-opacity="{opacity * 1.5}"/>
                <stop offset="0.5" stop-color="{bubble_accent}" stop-opacity="{opacity}"/>
                <stop offset="1" stop-color="{bubble_accent}" stop-opacity="0"/>
            </radialGradient>'''

            bubble = (
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{gradient_id})" />'
            )

            # Add subtle highlight
            highlight_cx = cx - r * 0.3
            highlight_cy = cy - r * 0.3
            highlight_r = r * 0.25
            highlight = f'<circle cx="{highlight_cx}" cy="{highlight_cy}" r="{highlight_r}" fill="white" opacity="0.2"/>'

            return gradient_def, bubble + highlight

        def rand_bezier():
            x1 = rng.randint(100, width - 100)
            y1 = rng.randint(100, height - 100)
            cx1 = rng.randint(100, width - 100)
            cy1 = rng.randint(100, height - 100)
            cx2 = rng.randint(100, width - 100)
            cy2 = rng.randint(100, height - 100)
            x2 = rng.randint(100, width - 100)
            y2 = rng.randint(100, height - 100)
            stroke = rng.choice([accent_a, accent_b, accent_c])
            stroke_width = rng.randint(2, 4)
            opacity = rng.uniform(0.2, 0.4)
            return f'<path d="M {x1} {y1} C {cx1} {cy1}, {cx2} {cy2}, {x2} {y2}" stroke="{stroke}" stroke-width="{stroke_width}" fill="none" opacity="{opacity}" />'

        # Create layers of shapes with varying counts
        layer_1 = [
            rng.choice([rand_rect, rand_circle, rand_polygon])()
            for _ in range(rng.randint(2, 3))
        ]
        layer_2 = [
            rng.choice([rand_ellipse, rand_triangle, rand_star])()
            for _ in range(rng.randint(2, 3))
        ]
        layer_3 = [
            rng.choice([rand_circle, rand_polygon])() for _ in range(rng.randint(1, 2))
        ]

        # Create bubbles
        bubble_gradients = []
        bubbles = []
        for _ in range(rng.randint(0, 5)):
            grad, bub = rand_bubble()
            bubble_gradients.append(grad)
            bubbles.append(bub)

        # Reduced accent lines
        accent_lines = [rand_bezier() for _ in range(rng.randint(1, 2))]

        # Create dynamic accent paths
        def create_accent_path():
            start_x = rng.randint(100, 300)
            start_y = rng.randint(height - 200, height - 80)
            mid_x = width // 2 + rng.randint(-150, 150)
            mid_y = rng.randint(180, 320)
            end_x = rng.randint(width - 300, width - 100)
            end_y = rng.randint(height - 200, height - 80)
            return f"M{start_x} {start_y} Q{mid_x} {mid_y} {end_x} {end_y}"

        accent_path_1 = create_accent_path()
        accent_path_2 = create_accent_path()

        # Generate SVG with proper XML declaration
        svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse">
            <stop offset="0" stop-color="{background_a}"/>
            <stop offset="1" stop-color="{background_b}"/>
        </linearGradient>
        <linearGradient id="accent" x1="0" y1="0" x2="{width}" y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stop-color="{accent_a}"/>
            <stop offset="0.5" stop-color="{accent_b}"/>
            <stop offset="1" stop-color="{accent_c}"/>
        </linearGradient>
        <radialGradient id="radial" cx="0.5" cy="0.5" r="0.5">
            <stop offset="0" stop-color="{accent_a}" stop-opacity="0.3"/>
            <stop offset="1" stop-color="{accent_b}" stop-opacity="0"/>
        </radialGradient>
        {"".join(bubble_gradients)}
    </defs>
    <rect width="{width}" height="{height}" fill="url(#bg)"/>
    <g opacity="0.28">
        {"".join(layer_1)}
    </g>
    <g opacity="0.24">
        {"".join(layer_2)}
    </g>
    <g opacity="0.18">
        {"".join(layer_3)}
    </g>
    <g>
        {"".join(bubbles)}
    </g>
    <g>
        {"".join(accent_lines)}
    </g>
    <path d="{accent_path_1}" stroke="url(#accent)" stroke-width="{rng.randint(4, 7)}" opacity="0.6"/>
    <path d="{accent_path_2}" stroke="{accent_a}" stroke-width="{rng.randint(2, 4)}" opacity="0.35"/>
    <circle cx="{rng.randint(200, width - 200)}" cy="{rng.randint(150, height - 150)}" r="{rng.randint(200, 350)}" fill="url(#radial)" opacity="0.4"/>
</svg>"""

        # Validate SVG length
        if len(svg) < 500:
            logger.error(f"SVG unexpectedly short for seed {seed}: {len(svg)} bytes")

        # Log successful generation
        logger.debug(f"Generated SVG for seed {seed}: {len(svg)} bytes")

        # Encode to UTF-8 bytes and return with proper headers
        svg_bytes = svg.encode("utf-8")
        response = HttpResponse(svg_bytes, content_type="image/svg+xml; charset=utf-8")
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["X-Content-Type-Options"] = "nosniff"

        return response

    except Exception as e:
        logger.exception(f"Failed to generate SVG for seed {seed}: {str(e)}")

        # Return a simple fallback SVG on error
        fallback_svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="1200" height="640" viewBox="0 0 1200 640" xmlns="http://www.w3.org/2000/svg">
    <rect width="1200" height="640" fill="#F8FAFC"/>
    <text x="600" y="320" text-anchor="middle" font-family="Arial" font-size="24" fill="#666">
        Image placeholder unavailable
    </text>
</svg>"""
        response = HttpResponse(
            fallback_svg.encode("utf-8"), content_type="image/svg+xml; charset=utf-8"
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response
