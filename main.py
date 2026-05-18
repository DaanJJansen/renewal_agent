"""
Microsoft Renewal Exam Automation
Uses Playwright (Firefox) + OpenAI GPT-4o to answer exam questions automatically.
"""

import os
import re
import json
import time
from dotenv import load_dotenv
from openai import OpenAI
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

load_dotenv()

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

if not AZURE_OPENAI_API_KEY:
    raise ValueError("AZURE_OPENAI_API_KEY not set. Copy .env.example to .env and fill in your key.")

client = OpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    base_url=f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}",
    default_query={"api-version": AZURE_OPENAI_API_VERSION},
    default_headers={"api-key": AZURE_OPENAI_API_KEY},
)


def ask_gpt(question: str, options: list[dict]) -> list[str]:
    """
    Ask GPT-4o which option(s) are correct.
    Returns a list of correct option labels (e.g. ['A', 'C']).
    """
    options_text = "\n".join(
        f"{opt['label']}. {opt['text']}" for opt in options
    )

    prompt = (
        "You are answering a Microsoft certification renewal exam question.\n"
        "Select the correct answer(s). "
        "Reply with ONLY a JSON array of the correct option labels, e.g. [\"A\"] or [\"A\",\"C\"].\n\n"
        f"Question:\n{question}\n\n"
        f"Options:\n{options_text}"
    )

    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()
    # Extract JSON array from the response
    match = re.search(r'\[.*?\]', raw, re.DOTALL)
    if not match:
        raise ValueError(f"GPT response could not be parsed: {raw}")
    return json.loads(match.group())


def extract_question(page) -> dict | None:
    """
    Extract the question text and answer options from the current page.
    Returns dict with 'question', 'options' (list of {label, text, element}), 'type'.
    Returns None if no question is found.
    """
    # Try common Microsoft Learn / certification exam selectors
    question_selectors = [
        "[data-automation-id='question-text']",
        ".question-text",
        "[class*='questionText']",
        "[class*='question-body']",
        "fieldset legend",
        "[role='heading'][aria-level]",
        ".exam-question",
    ]

    question_text = None
    for sel in question_selectors:
        el = page.query_selector(sel)
        if el:
            question_text = el.inner_text().strip()
            break

    if not question_text:
        # Fallback: grab all visible text in main content area
        main = page.query_selector("main") or page.query_selector("body")
        if main:
            question_text = main.inner_text()[:2000].strip()

    # Find radio buttons
    radio_inputs = page.query_selector_all("input[type='radio']")
    checkbox_inputs = page.query_selector_all("input[type='checkbox']")

    inputs = radio_inputs if radio_inputs else checkbox_inputs
    input_type = "radio" if radio_inputs else "checkbox"

    if not inputs:
        print("  No answer inputs found on this page.")
        return None

    options = []
    labels = "ABCDEFGHIJKLMNOP"
    for i, el in enumerate(inputs):
        label_el = None
        el_id = el.get_attribute("id")
        if el_id:
            label_el = page.query_selector(f"label[for='{el_id}']")
        if not label_el:
            # Try parent label
            label_el = el.evaluate_handle("el => el.closest('label')").as_element()
        if not label_el:
            # Try next sibling text
            label_el = el.evaluate_handle(
                "el => el.parentElement"
            ).as_element()

        option_text = label_el.inner_text().strip() if label_el else f"Option {i+1}"
        options.append({
            "label": labels[i],
            "text": option_text,
            "element": el,
        })

    return {
        "question": question_text,
        "options": options,
        "type": input_type,
    }


def select_answers(page, question_data: dict, correct_labels: list[str]):
    """Click the radio buttons or checkboxes for the correct answers."""
    for opt in question_data["options"]:
        if opt["label"] in correct_labels:
            print(f"  Selecting option {opt['label']}: {opt['text'][:80]}")
            try:
                opt["element"].scroll_into_view_if_needed()
                opt["element"].click(force=True)
                time.sleep(0.3)
            except Exception as e:
                print(f"  Warning: could not click option {opt['label']}: {e}")


def click_next(page) -> bool:
    """Click the Next / Check Answer / Submit button. Returns False if not found."""
    next_selectors = [
        "button:has-text('Next')",
        "button:has-text('next')",
        "button:has-text('Submit')",
        "button:has-text('Check answer')",
        "button:has-text('Continue')",
        "[data-automation-id='next-button']",
        "[aria-label*='next' i]",
        "[aria-label*='submit' i]",
        "input[type='submit']",
    ]
    for sel in next_selectors:
        btn = page.query_selector(sel)
        if btn and btn.is_visible() and btn.is_enabled():
            print(f"  Clicking: {btn.inner_text().strip()}")
            btn.click()
            return True
    return False


def is_exam_finished(page) -> bool:
    """Detect if the exam results/summary page has been reached."""
    finish_signals = [
        "your score",
        "exam results",
        "congratulations",
        "you passed",
        "you did not pass",
        "results summary",
        "score report",
    ]
    body_text = page.inner_text("body").lower()
    return any(sig in body_text for sig in finish_signals)


def run_exam(url: str):
    with sync_playwright() as p:
        print("Launching Firefox browser...")
        browser = p.firefox.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"Navigating to: {url}")
        page.goto(url, timeout=60_000)

        print("\nIf you need to log in, please do so now in the browser window.")
        print("Navigate to the first question, then come back here and press ENTER.")
        input("Press ENTER when you are on the first question...")

        question_number = 1
        while True:
            print(f"\n--- Question {question_number} ---")

            if is_exam_finished(page):
                print("Exam finished! Results page detected.")
                break

            page.wait_for_load_state("networkidle", timeout=15_000)
            time.sleep(1)

            question_data = extract_question(page)
            if not question_data:
                print("Could not extract question. Check the browser window.")
                action = input("Type 'skip' to try next, or 'quit' to exit: ").strip().lower()
                if action == "quit":
                    break
                click_next(page)
                time.sleep(2)
                question_number += 1
                continue

            print(f"  Q: {question_data['question'][:200]}")
            print(f"  Type: {question_data['type']} | Options: {len(question_data['options'])}")
            for opt in question_data["options"]:
                print(f"    {opt['label']}. {opt['text'][:100]}")

            try:
                correct = ask_gpt(question_data["question"], question_data["options"])
                print(f"  GPT answer(s): {correct}")
            except Exception as e:
                print(f"  GPT error: {e}")
                correct = []

            if correct:
                select_answers(page, question_data, correct)
                time.sleep(0.5)

            if not click_next(page):
                print("  No Next button found. Check the browser window.")
                action = input("Type 'continue' to keep going or 'quit' to exit: ").strip().lower()
                if action == "quit":
                    break

            time.sleep(2)
            question_number += 1

        print("\nDone. Press ENTER to close the browser.")
        input()
        browser.close()


if __name__ == "__main__":
    print("=== Microsoft Renewal Exam Automation ===")
    exam_url = input("Enter the exam URL (or press ENTER to use about:blank and navigate manually): ").strip()
    if not exam_url:
        exam_url = "about:blank"
    run_exam(exam_url)
