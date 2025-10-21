from playwright.sync_api import sync_playwright
from scripts.log_utils import install_global_exception_logger, setup_logging

BEST_PAGE_URL = (
    "https://display.wconcept.co.kr/rn/best?displayCategoryType=ALL&displaySubCategoryType=ALL&gnbType=Y"
)

PAT = "gw-front.wconcept.co.kr/display/api/best/v1"

logger = setup_logging("debug_wconcept_capture")
install_global_exception_logger(logger)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(locale="ko-KR", timezone_id="Asia/Seoul")
    page = context.new_page()

    keys = set()

    def on_request(req):
        if PAT in req.url:
            h = {k.lower(): v for k, v in (req.headers or {}).items()}
            if 'x-api-key' in h:
                keys.add(h['x-api-key'])
            logger.info("REQ: %s %s x-api-key:%s", req.method, req.url, h.get('x-api-key'))

    def on_response(res):
        if PAT in res.url:
            logger.info("RES: %s %s", res.status, res.url)

    page.on("request", on_request)
    page.on("response", on_response)

    try:
        page.goto(BEST_PAGE_URL, wait_until="networkidle", timeout=30000)
        # Allow time for any lazy loading
        page.wait_for_timeout(5000)
    except Exception:
        logger.exception("페이지 탐색 중 오류")
        raise

    logger.info("Captured keys: %s", list(keys))

    context.close()
    browser.close()
