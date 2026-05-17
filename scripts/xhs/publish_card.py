"""文字配图发布 — 小红书卡片模板图文创作。

将标题和正文渲染到风格化的卡片上，作为图片发布，
无需上传真实图片。与"上传图文"模式下发布真实图片不同，
文字配图模式内嵌在 creator 发布页中，先选择"文字配图" tab，
填写内容后选择卡片模板，点击"下一步"进入正式发布表单。
"""

from __future__ import annotations

import json
import logging
import time

from .cdp import Page
from .errors import PublishError
from .urls import PUBLISH_URL

logger = logging.getLogger(__name__)


# ========== 页面导航 ==========


def _navigate_to_publish_page(page: Page) -> None:
    """导航到 creator 发布页。"""
    page.navigate(PUBLISH_URL)
    page.wait_for_load(timeout=300)
    time.sleep(3)
    page.wait_dom_stable()
    time.sleep(2)


def _click_card_tab(page: Page) -> None:
    """点击"文字配图"子选项。

    文字配图不是独立 TAB，而是"上传图文" TAB 下的子选项。
    流程：先点击"上传图文" creator-tab，再在展开的面板中点击"文字配图"按钮。

    Raises:
        PublishError: 未找到上传图文 tab 或文字配图按钮。
    """
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        # Step 1: 点击"上传图文" creator-tab
        tab_clicked = page.evaluate(
            """
            (() => {
                const tabs = document.querySelectorAll('div.creator-tab');
                for (const tab of tabs) {
                    const span = tab.querySelector('span.title');
                    const text = span ? span.textContent.trim() : tab.textContent.trim();
                    if (text === '上传图文' || text === '图文') {
                        const rect = tab.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        const cs = window.getComputedStyle(tab);
                        if (cs.display === 'none' || cs.visibility === 'hidden') continue;
                        tab.click();
                        return true;
                    }
                }
                return false;
            })()
            """
        )
        if not tab_clicked:
            time.sleep(0.3)
            continue
        time.sleep(1.5)

        # Step 2: 点击"文字配图" button（在上传图文面板内）
        btn_clicked = page.evaluate(
            """
            (() => {
                const buttons = document.querySelectorAll(
                    'button.d-button, button.upload-button, button');
                for (const btn of buttons) {
                    const text = (btn.textContent || '').trim();
                    if (text === '文字配图') {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        const cs = window.getComputedStyle(btn);
                        if (cs.display === 'none' || cs.visibility === 'hidden') continue;
                        btn.scrollIntoView({block: 'center'});
                        btn.click();
                        return true;
                    }
                }
                return false;
            })()
            """
        )
        if btn_clicked:
            logger.info("已点击文字配图按钮")
            time.sleep(2)
            return
        time.sleep(0.3)

    raise PublishError("未找到文字配图发布选项，请确认 creator 页面支持此功能")


# ========== 内容填写 ==========


def fill_card_content(page: Page, title: str, content: str) -> None:
    """在文字配图模式下填写正文内容。

    文字配图模式没有独立的标题输入框，正文填写到 tiptap 编辑器中。
    标题在用户确认预览后，通过"下一步"进入发布表单时填写。

    Args:
        page: CDP 页面对象。
        title: 笔记标题（在此模式下不会被直接填写，留待发布表单）。
        content: 正文内容（显示在卡片上）。

    Raises:
        PublishError: 未找到正文输入框。
    """
    text_json = json.dumps(content)
    filled = page.evaluate(
        f"""
        (() => {{
            const text = {text_json};
            // 策略1: tiptap ProseMirror 编辑器（文字配图模式）
            const tiptap = document.querySelector('.tiptap.ProseMirror');
            if (tiptap) {{
                tiptap.focus();
                tiptap.innerHTML = '<p>' + text.replace(/\\n/g, '</p><p>') + '</p>';
                tiptap.dispatchEvent(new Event('input', {{bubbles: true}}));
                return true;
            }}
            // 策略2: QL 编辑器
            const ql = document.querySelector('div.ql-editor');
            if (ql) {{
                ql.focus();
                ql.innerHTML = '<p>' + text.replace(/\\n/g, '</p><p>') + '</p>';
                ql.dispatchEvent(new Event('input', {{bubbles: true}}));
                return true;
            }}
            return false;
        }})()
        """
    )
    if not filled:
        raise PublishError("未找到正文输入框")

    time.sleep(1)
    logger.info("文字配图正文已填写")


# ========== 卡片生成 ==========


def _click_generate_image(page: Page) -> bool:
    """点击"生成图片"按钮，触发卡片模板生成。

    在文字配图文本编辑器中点击"生成图片"，页面右侧会生成
    卡片预览图像和可用模板列表。

    Returns:
        True 按钮已点击。
    """
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        clicked = page.evaluate(
            """
            (() => {
                // 找包含"生成图片"的按钮元素，跳过 disabled 状态
                // DOM: div.edit-text-button-container > div.edit-text-button > span
                const selectors = [
                    'div.edit-text-button',
                    'div.edit-text-button-container',
                    'button'
                ];
                for (const sel of selectors) {
                    for (const btn of document.querySelectorAll(sel)) {
                        const text = (btn.textContent || '').trim();
                        if (!text.includes('生成图片')) continue;
                        // 检查 disabled 状态
                        if (btn.classList.contains('disabled')) continue;
                        if (btn.querySelector('.disabled')) continue;
                        const rect = btn.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) continue;
                        const cs = window.getComputedStyle(btn);
                        if (cs.display === 'none' || cs.visibility === 'hidden') continue;
                        btn.click();
                        return true;
                    }
                }
                return false;
            })()
            """
        )
        if clicked:
            logger.info("已点击生成图片按钮")
            time.sleep(3)
            return True
        time.sleep(0.5)
    logger.warning("生成图片按钮未就绪（可能仍为 disabled）")
    return False


# ========== 卡片模板浏览 & 选择 ==========


def get_available_templates(page: Page) -> dict:
    """获取可用的卡片模板列表。

    返回结构：
    {
        "categories": [],
        "current_category": "",
        "templates": ["基础", "涂鸦", "备忘", "边框", "清新", ...]
    }

    Returns:
        模板数据字典；无法获取时返回空结构。
    """
    result = page.evaluate(
        """
        (() => {
            const data = {categories: [], current_category: '', templates: []};
            const names = document.querySelectorAll('.cover-name');
            names.forEach(el => {
                const text = (el.textContent || '').trim();
                if (text) data.templates.push(text);
            });
            return JSON.stringify(data);
        })()
        """
    )

    if not result:
        return {"categories": [], "current_category": "", "templates": []}

    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {"categories": [], "current_category": "", "templates": []}


def select_category(page: Page, category_name: str) -> bool:
    """切换卡片模板分类。

    当前页面版本没有分类 TAB，总是返回 False。
    可在切换分类后重新调用 get_available_templates 获取模板列表。

    Returns:
        False（无分类功能）。
    """
    logger.warning("当前页面版本不支持模板分类切换")
    return False


def select_template(page: Page, template_name: str) -> bool:
    """选择指定名称的卡片模板。

    Args:
        page: CDP 页面对象。
        template_name: 模板名称（如"基础""涂鸦"）。

    Returns:
        True 选择成功。
    """
    clicked = page.evaluate(
        f"""
        (() => {{
            const tName = {json.dumps(template_name)};
            const containers = document.querySelectorAll('.cover-item-container');
            for (const container of containers) {{
                const nameEl = container.querySelector('.cover-name');
                const name = nameEl ? (nameEl.textContent || '').trim() : '';
                if (name === tName) {{
                    container.scrollIntoView({{block: 'center'}});
                    container.click();
                    return true;
                }}
            }}
            return false;
        }})()
        """
    )
    if clicked:
        time.sleep(1)
        logger.info("已选择卡片模板: %s", template_name)
    else:
        logger.warning("未找到卡片模板: %s", template_name)
    return clicked


# ========== 配色切换 ==========


def change_template_color(page: Page) -> list[str]:
    """点击当前选中模板的"换配色"按钮，返回可选颜色列表。

    "换配色"按钮位于当前选中模板（.cover-item.active）内部，
    类型为 div.change。

    Returns:
        可选颜色名称列表；无配色选项时返回空列表。
    """
    clicked = page.evaluate(
        """
        (() => {
            // 找活跃模板内的"换配色"按钮
            const active = document.querySelector('.cover-item.active');
            if (!active) return null;
            const changeBtn = active.querySelector('div.change');
            if (changeBtn) {
                changeBtn.click();
                return 'opened';
            }
            return 'no_button';
        })()
        """
    )

    if clicked == "no_button":
        logger.info("当前模板无换配色选项")
        return []

    time.sleep(0.8)

    colors = page.evaluate(
        """
        (() => {
            const items = document.querySelectorAll(
                '[class*="color-circle"], [class*="color-item"], '
                + '[class*="color-option"]'
            );
            return Array.from(items).map(el => {
                const style = el.getAttribute('style') || '';
                const cls = el.className || '';
                const text = (el.textContent || '').trim();
                return text || cls || style.match(/background[^:]*:([^;]+)/)?.[1]?.trim() || '';
            }).filter(Boolean);
        })()
        """
    )

    if colors:
        logger.info("换配色已打开，可选颜色: %s", colors)
    else:
        logger.info("换配色已点击")
    return colors


def select_color(page: Page, color_value: str) -> bool:
    """从配色选择器中点选指定颜色。

    Args:
        page: CDP 页面对象。
        color_value: 颜色名或色值。

    Returns:
        True 选择成功。
    """
    clicked = page.evaluate(
        f"""
        (() => {{
            const items = document.querySelectorAll(
                '[class*="color-circle"], [class*="color-item"], '
                + '[class*="color-option"]'
            );
            for (const el of items) {{
                const text = (el.textContent || '').trim();
                const style = (el.getAttribute('style') || '').toLowerCase();
                const cVal = {json.dumps(color_value)};
                if (text === cVal || style.includes(cVal)) {{
                    el.click();
                    return true;
                }}
            }}
            return false;
        }})()
        """
    )
    if clicked:
        time.sleep(1)
        logger.info("已切换配色: %s", color_value)
    return clicked


# ========== 确认预览 ==========


def confirm_preview(page: Page) -> None:
    """点击"下一步"按钮确认卡片选择，进入正式发布表单。

    "下一步"按钮位于 .overview-footer 中的 button.d-button。

    Raises:
        PublishError: 未找到"下一步"按钮。
    """
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        next_btn = page.evaluate(
            """
            (() => {
                const footer = document.querySelector('.overview-footer');
                if (!footer) return false;
                const btns = footer.querySelectorAll('button');
                for (const btn of btns) {
                    const text = (btn.textContent || '').trim();
                    if (text === '下一步') {
                        btn.click();
                        return true;
                    }
                }
                return false;
            })()
            """
        )
        if next_btn:
            logger.info("已点击下一步按钮")
            time.sleep(3)
            page.wait_dom_stable()
            return
        time.sleep(0.5)

    raise PublishError("未找到下一步按钮")


# ========== 组合流程 ==========


def fill_card_publish_form(page: Page, title: str, content: str) -> dict:
    """完整的文字配图表单填写流程。

    导航到发布页 → 点击文字配图 tab → 填写内容 → 等待卡片生成 → 返回模板列表。

    Args:
        page: CDP 页面对象。
        title: 笔记标题。
        content: 正文内容。

    Returns:
        {
            "categories": [],
            "current_category": "",
            "templates": [...]
        }
    """
    _navigate_to_publish_page(page)
    _click_card_tab(page)
    fill_card_content(page, title, content)

    # 生成卡片图片，等待模板列表出现
    _click_generate_image(page)
    time.sleep(3)
    page.wait_dom_stable()

    templates = get_available_templates(page)
    logger.info(
        "文字配图表单已填写，可用模板: %s",
        templates.get("templates", []),
    )
    return templates


# ========== 发布 ==========


def click_publish(page: Page) -> None:
    """在文字配图发布表单中点击发布按钮。

    文字配图模式的发布按钮位于 <xhs-publish-btn> 自定义元素内，
    通过调用其 _onPublish() 方法触发发布。

    Raises:
        PublishError: 未找到发布按钮或发布失败。
    """
    result = page.evaluate(
        """
        (() => {
            const btn = document.querySelector('xhs-publish-btn');
            if (!btn) return JSON.stringify({found: false, reason: 'no_element'});
            if (typeof btn._onPublish !== 'function') {
                return JSON.stringify({found: true, reason: 'no_handler'});
            }
            try {
                const ret = btn._onPublish();
                return JSON.stringify({found: true, called: true, result: ret});
            } catch (e) {
                return JSON.stringify({found: true, called: true, error: e.message});
            }
        })()
        """
    )
    if not result:
        raise PublishError("未找到 xhs-publish-btn 元素")

    data = json.loads(result)

    if not data.get("found"):
        raise PublishError("未找到发布按钮 (xhs-publish-btn)")
    if data.get("reason") == "no_handler":
        raise PublishError("发布按钮就绪但 _onPublish 方法不可用")
    if not data.get("called"):
        raise PublishError("发布调用失败")

    time.sleep(3)
    logger.info("文字配图发布完成")

    # 检查是否跳转到成功页
    success_url = page.evaluate("window.location.href")
    if "/publish/success" in success_url:
        logger.info("已跳转到发布成功页: %s", success_url)
    else:
        logger.warning("发布后 URL 未变化: %s", success_url)
