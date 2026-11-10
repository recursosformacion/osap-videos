from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

from app import BASE_DIR


def render_base() -> str:
    env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")), autoescape=True)
    env.globals["url_for"] = lambda name, **kwargs: f"/static/{kwargs['path']}"
    template = env.get_template("base.html")
    return template.render(
        version="test",
        request=SimpleNamespace(url=SimpleNamespace(path="/")),
        work_id="123",
        resource_id="456",
        osap_url="https://app.example",
        osap_work_url="https://app.example/obra/123",
        login_url="/login",
        register_url="/register",
        user=None,
        user_name="",
    )


def test_menu_is_rendered_in_a_single_top_header() -> None:
    html = render_base()
    assert '<header class="site-header">' in html
    assert '<nav class="main-nav"' in html
    assert 'class="sidebar"' not in html
    assert html.index('class="site-header"') < html.index('class="layout"')


def test_vertical_ad_rail_is_on_the_right_and_targets_sidebar_placement() -> None:
    html = render_base()
    layout = html[html.index('class="layout"') :]
    assert '<aside class="ad-rail"' in layout
    assert 'data-ad-placement="sidebar"' in layout
    assert 'data-page-type="video_results"' in layout
    assert 'class="ad-slot ad-tall"' in layout
    assert html.index('class="main"') < html.index('class="ad-rail"')


def test_vertical_ad_rail_is_skipped_on_narrow_screens() -> None:
    css = (BASE_DIR / "static" / "app.css").read_text(encoding="utf-8")
    assert "@media (max-width: 1000px)" in css
    assert ".ad-rail { display: none; }" in css
    assert "grid-template-columns: minmax(0, 1fr) 300px" in css
