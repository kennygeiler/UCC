"""ASP.NET grid pagination helpers for Playwright pages."""

from __future__ import annotations

# JS: read current/total page from grid footer ("Page 2/5" pattern).
PAGER_PAGE_INFO_JS = """(gridSelector) => {
    const grid = document.querySelector(gridSelector);
    if (!grid) return { current: 0, total: 0 };
    const root = grid.closest('table') || grid.parentElement || grid;
    const scope = root.parentElement || document;
    const text = scope.innerText || '';
    const match = text.match(/Page\\s+(\\d+)\\s*\\/\\s*(\\d+)/i);
    if (match) {
        return { current: parseInt(match[1], 10), total: parseInt(match[2], 10) };
    }
    return { current: 0, total: 0 };
}"""

# JS: ASP.NET __doPostBack for GridView pager (NJ pattern).
ASP_NET_POSTBACK_NEXT_JS = """(gridSelector) => {
    const grid = document.querySelector(gridSelector);
    if (!grid) return false;
    const cells = document.querySelectorAll('[id*=' + JSON.stringify('Results') + '] tr:last-child td, tr:last-child td');
    let nextPage = 0;
    for (const cell of cells) {
        const text = cell.innerText || '';
        const match = text.match(/Page\\s+(\\d+)\\/(\\d+)/);
        if (match) {
            const current = parseInt(match[1], 10);
            const total = parseInt(match[2], 10);
            if (current < total) {
                nextPage = current + 1;
                break;
            }
        }
    }
    if (!nextPage) return false;
    const gridId = grid.id.replace(/_/g, '$');
    if (typeof __doPostBack === 'function') {
        __doPostBack(gridId, 'Page$' + nextPage);
        return true;
    }
    return false;
}"""

# NY xhtml_grid: click numeric pager link or "next" in .pagination / datagrid footer.
XHTML_GRID_NEXT_JS = """() => {
    const info = (() => {
        const text = document.body.innerText || '';
        const match = text.match(/Page\\s+(\\d+)\\s*\\/\\s*(\\d+)/i)
            || text.match(/(\\d+)\\s+of\\s+(\\d+)/i);
        if (match) {
            const current = parseInt(match[1], 10);
            const total = parseInt(match[2], 10);
            if (current < total) return current + 1;
        }
        return 0;
    })();
    if (!info) {
        const next = document.querySelector(
            '#xhtml_grid ~ .pagination a.next:not(.disabled), ' +
            '.datagrid-pager a.l-btn-icon-next:not(.l-btn-disabled), ' +
            'a[title="Next"]:not(.disabled)'
        );
        if (next) { next.click(); return true; }
        return false;
    }
    const links = document.querySelectorAll(
        '#xhtml_grid ~ .pagination a, .datagrid-pager a, .pagination a'
    );
    for (const a of links) {
        if ((a.innerText || '').trim() === String(info)) {
            a.click();
            return true;
        }
    }
    const nextBtn = document.querySelector(
        '.datagrid-pager a.l-btn-icon-next:not(.l-btn-disabled)'
    );
    if (nextBtn) { nextBtn.click(); return true; }
    return false;
}"""


async def read_pager_info(page, grid_selector: str) -> tuple[int, int]:
    """Return (current_page, total_pages); zeros if unknown."""
    info = await page.evaluate(PAGER_PAGE_INFO_JS, grid_selector)
    return int(info.get("current", 0)), int(info.get("total", 0))


async def aspnet_grid_next_page(page, grid_selector: str) -> bool:
    """Trigger next page on ASP.NET GridView; wait for network idle."""
    clicked = await page.evaluate(
        """(sel) => {
            const grid = document.querySelector(sel);
            if (!grid) return false;
            const cells = document.querySelectorAll('[id*=orgResultsGridView] tr:last-child td, tr:last-child td');
            let nextPage = 0;
            for (const cell of cells) {
                const text = cell.innerText || '';
                const match = text.match(/Page\\s+(\\d+)\\/(\\d+)/);
                if (match) {
                    const current = parseInt(match[1], 10);
                    const total = parseInt(match[2], 10);
                    if (current < total) { nextPage = current + 1; break; }
                }
            }
            if (!nextPage) return false;
            const gridId = grid.id.replace(/_/g, '$');
            if (typeof __doPostBack === 'function') {
                __doPostBack(gridId, 'Page$' + nextPage);
                return true;
            }
            return false;
        }""",
        grid_selector,
    )
    if not clicked:
        return False
    await page.wait_for_load_state("networkidle", timeout=30_000)
    await page.wait_for_timeout(1_000)
    return True


async def xhtml_grid_next_page(page) -> bool:
    """Advance NY-style xhtml_grid pager."""
    clicked = await page.evaluate(XHTML_GRID_NEXT_JS)
    if not clicked:
        return False
    await page.wait_for_load_state("networkidle", timeout=45_000)
    await page.wait_for_timeout(500)
    return True
