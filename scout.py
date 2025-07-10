# Import all necessary libraries
import requests
from bs4 import BeautifulSoup, Tag
import urllib.parse
import sqlite3
import google.generativeai as genai
import time
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import psycopg2

from google import genai
from google.genai import types

# --- IMPORTS FOR SELENIUM & CERTIFICATES ---
import os
import certifi
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from dotenv import load_dotenv
load_dotenv()

# --- CONFIGURATION ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_CONNECTION_URI = os.getenv("SUPABASE_CONNECTION_URI") # New variable for the database

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
}

def get_db_connection():
    """
    Establishes a connection to the Supabase PostgreSQL database,
    with a retry mechanism for resilience.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(SUPABASE_CONNECTION_URI)
            return conn
        except Exception as e:
            print(f"Database connection attempt {attempt + 1} of {max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep()  # Wait for 3 seconds before retrying
            else:
                print("FATAL ERROR: Could not connect to the database after multiple retries.")
    return None


def setup_database():
    """
    Ensures the 'briefings' table exists in the PostgreSQL database.
    The table should already be created via the Supabase SQL Editor.
    This function now just verifies the connection.
    """
    print("Verifying database connection...")
    conn = get_db_connection()
    if conn:
        print("Database connection successful.")
        conn.close()
    else:
        print("Database connection failed. Please check your SUPABASE_CONNECTION_URI in the .env file.")
        exit()  # Exit if we can't connect to the DB


def is_item_processed(identifier: str) -> bool:
    """Checks if a generic identifier exists in the PostgreSQL database."""
    conn = get_db_connection()
    if not conn: return True  # Assume processed if we can't connect, to prevent errors

    processed = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM briefings WHERE processed_identifier = %s", (identifier,))
            result = cur.fetchone()
            if result:
                processed = True
    except Exception as e:
        print(f"ERROR checking database for identifier '{identifier}': {e}")
    finally:
        if conn:
            conn.close()
    return processed


def add_briefing_to_db(briefing_data: dict):
    """Adds a new parsed briefing to the PostgreSQL database."""
    conn = get_db_connection()
    if not conn: return

    identifier = briefing_data.get('identifier')
    if is_item_processed(identifier):
        print(f"      -> Identifier '{identifier}' already exists. Skipping database insert.")
        return
    processed_data = {k.lower().replace(' ', '_'): v for k, v in briefing_data.items()}

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO briefings 
                (processed_identifier, competitor, product_line, feature_update, summary, pm_analysis, source_url) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                identifier, processed_data.get('competitor'),
                processed_data.get('product_line'), processed_data.get('feature_update'),
                processed_data.get('summary'), processed_data.get('pm_analysis'),
                processed_data.get('source_url')
            ))
        conn.commit()
    except Exception as e:
        print(f"ERROR inserting briefing into database: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

# --- HELPER & UTILITY FUNCTIONS ---
def clean_html_content(soup_container: BeautifulSoup, elements_to_remove: list):
    if not soup_container: return
    for element_spec in elements_to_remove:
        for found_element in soup_container.find_all(element_spec.get("tag"), class_=element_spec.get("class"),
                                                     id=element_spec.get("id")):
            if found_element: found_element.decompose()


def get_page_source_with_selenium(url: str) -> str:
    print(f"    -> Loading page with Selenium browser: {url}")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    service = ChromeService(ChromeDriverManager().install())
    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(url)
        time.sleep(5)
        page_source = driver.page_source
        print("    -> Page loaded successfully.")
        return page_source
    except Exception as e:
        print(f"     ERROR: Selenium failed to load page. Details: {e}")
        return ""
    finally:
        if driver: driver.quit()


def scrape_article_content(url: str) -> str:
    if not url: return ""
    html_content = get_page_source_with_selenium(url)
    if not html_content: return f"WARNING: Content could not be loaded from {url}."
    soup = BeautifulSoup(html_content, 'html.parser')
    container = soup.find('div', id='article-main') or soup.find('div', id='dev-main')
    if container:
        clean_html_content(container, [{"tag": "div", "id": "breadcrumb"}, {"tag": "div", "id": "bottom_nav"}])
        return container.get_text(separator=' ', strip=True)
    return f"WARNING: Main content container ('article-main' or 'dev-main') not found on {url}."


# --- AI PROMPTS & DISPATCHER (Restored to Modular Structure) ---

def get_braze_prompt(context: str, competitor_name: str) -> str:
    """The detailed, fine-tuned prompt for analyzing Braze's articles."""
    return f"""
    You are an expert Product Manager specializing in competitive intelligence for the Marketing Automation industry. Your analysis is critical for shaping product strategy.

    ### CONTEXT

        - MY COMPANY: MoEngage

        - COMPETITOR: {competitor_name}

        - ANALYSIS GOAL: To dissect a competitor's feature update and provide a concise intelligence briefing for internal product teams.



    ### TASK

        Your task is to analyze the provided article text about a new feature update from the competitor. Follow these steps precisely:

            1.Read the `ARTICLE_TEXT` to understand the core update. If the `ARTICLE_TEXT` is ambiguous or lacks detail, use the `DETAILED ARTICLE` for clarification .

            2.First, synthesize the information into a clear `FEATURE_UPDATE` title and a `SUMMARY`.

            3.Next, based on your analysis of the update's primary function and benefit to the user, classify it into **one and only one** `PRODUCT LINE` from the list below.

            4.Finally, provide a concise `PM ANALYSIS` from the perspective of MoEngage.

    ### PRODUCT LINE CATEGORIES
        -**Push:** Features related to push notifications and associated SDK updates.
        -**Email:** Features related to email campaigns, templates, and delivery.
        -**SMS:** Features related to SMS marketing.
        -**In-App:** Features related to in-app messages and associated SDK updates.
        -**OSM:** Features related to On-Site Messaging and associated SDK updates.
        -**Web Personalization (WebP):** Features that enable real-time personalization of website or web-app content by dynamically modifying web elements based on user data.
        -**Cards:** Features related to Iterable Cards, content cards, or similar card-based messaging and associated SDK updates.
        -**Content Management:** Features related to creating, managing, and reusing content across channels, such as Snippets, a central template manager, or landing page builders.
        -**Flows:** Features related to journey orchestration, visual workflows, or automation canvases.
        -**Campaign Management:** Channel-agnostic features for executing, measuring, and governing campaigns. This includes capabilities like global control groups, cross-channel performance reporting, or message archival for compliance. 
        -**Data:** Features related to data ingestion, management, architecture, and associated SDK updates.
        -**Segmentation:** Features related to audience creation, filtering, and predictive segmentation.
        -**Analyze:** Features related to product analytics, such as user behavior analysis, event funnels, retention charts, path analysis, and other reporting capabilities that directly compete with tools like Amplitude.
        -**ML or AI:** Features that explicitly leverage Machine Learning or Artificial Intelligence to automate decisions, predict user behavior, or optimize campaign performance.
        -**Partner Integrations:** New or enhanced integrations with third-party platforms (e.g., CDPs, analytics tools, etc.).
        -**WhatsApp:** Features specifically for the WhatsApp channel.
        -**RCS:** Features related to Rich Communication Services.
        -**Other Channels:** Introduction of entirely new messaging channels (e.g., TikTok DMs, etc.).
        -**Settings:** Updates related to administrative or configuration sections of the platform, such as account settings, user permissions, or security configurations.
        -**Miscellaneous & Others:** General platform updates, UI enhancements, or other features that do not fit into the above categories.
    
        **Tie-Breaking Rule:** If an update spans multiple categories, choose the one that represents the **primary customer benefit** or the area of the platform most directly impacted. For example, 

            - a new data integration for better segmentation should be classified as 'Partner Integrations', not 'Segmentation'.

            - a new template category added to Whatsapp mainly for a provider called Karix should be be classified as 'WhatsApp', not 'Partner Integrations'
            
            - a new global control group feature is 'Campaign Management'. 
            
            - An AI feature to optimize email subject lines should be 'ML or AI', not 'Email'.

    ### OUTPUT FORMAT

        Structure your response EXACTLY as follows. Do not add any conversational text, introductions, or apologies.

            COMPETITOR: {competitor_name}

            PRODUCT LINE: [The single most relevant product line from the list]

            FEATURE_UPDATE: [A short, descriptive title for the new feature or update]

            SUMMARY: [A 2-3 sentence summary explaining what the new feature does and its value to customers.]

            PM ANALYSIS: [A 1-2 sentence analysis of the strategic implication for MoEngage. Consider whether this is a catch-up feature, an innovation, a threat to our market position, or an opportunity we can learn from.]

    ---

    ### INPUT TEXTS

    #### ARTICLE_TEXT

        {context}
    """

def get_iterable_prompt(context: str, competitor_name: str) -> str:
    """An adapted prompt for Iterable's release note style."""
    return f"""
    You are an expert Product Manager specializing in competitive intelligence for the Marketing Automation industry. Your analysis is critical for shaping product strategy.

    ### CONTEXT

        - MY COMPANY: MoEngage

        - COMPETITOR: {competitor_name}

        - ANALYSIS GOAL: To dissect a competitor's feature update and provide a concise intelligence briefing for internal product teams.



    ### TASK

        Your task is to analyze the provided article text about a new feature update from the competitor. Follow these steps precisely:

            1.Read the `ARTICLE_TEXT` to understand the core update.

            2.First, synthesize the information into a clear `FEATURE_UPDATE` title and a `SUMMARY`.

            3.Next, based on your analysis of the update's primary function and benefit to the user, classify it into **one and only one** `PRODUCT_LINE` from the list below.

            4.Finally, provide a concise `PM_ANALYSIS` from the perspective of MoEngage.

    ### PRODUCT LINE CATEGORIES

        -**Push:** Features related to push notifications and associated SDK updates.
        -**Email:** Features related to email campaigns, templates, and delivery.
        -**SMS:** Features related to SMS marketing.
        -**In-App:** Features related to in-app messages and associated SDK updates.
        -**OSM:** Features related to On-Site Messaging and associated SDK updates.
        -**Web Personalization (WebP):** Features that enable real-time personalization of website or web-app content by dynamically modifying web elements based on user data.
        -**Cards:** Features related to Iterable Cards, content cards, or similar card-based messaging and associated SDK updates.
        -**Content Management:** Features related to creating, managing, and reusing content across channels, such as Snippets, a central template manager, or landing page builders.
        -**Flows:** Features related to journey orchestration, visual workflows, or automation canvases.
        -**Campaogn Management:** Channel-agnostic features for executing, measuring, and governing campaigns. This includes capabilities like global control groups, cross-channel performance reporting, or message archival for compliance. 
        -**Data:** Features related to data ingestion, management, architecture, and associated SDK updates.
        -**Segmentation:** Features related to audience creation, filtering, and predictive segmentation.
        -**Analyze:** Features related to product analytics, such as user behavior analysis, event funnels, retention charts, path analysis, and other reporting capabilities that directly compete with tools like Amplitude.
        -**ML or AI:** Features that explicitly leverage Machine Learning or Artificial Intelligence to automate decisions, predict user behavior, or optimize campaign performance.
        -**Partner Integrations:** New or enhanced integrations with third-party platforms (e.g., CDPs, analytics tools, etc.).
        -**WhatsApp:** Features specifically for the WhatsApp channel.
        -**RCS:** Features related to Rich Communication Services.
        -**Other Channels:** Introduction of entirely new messaging channels (e.g., TikTok DMs, etc.).
        -**Settings:** Updates related to administrative or configuration sections of the platform, such as account settings, user permissions, or security configurations.
        -**Miscellaneous & Others:** General platform updates, UI enhancements, or other features that do not fit into the above categories.
    
        **Tie-Breaking Rule:** If an update spans multiple categories, choose the one that represents the **primary customer benefit** or the area of the platform most directly impacted. For example, 

            - a new data integration for better segmentation should be classified as 'Partner Integrations', not 'Segmentation'.

            - a new template category added to Whatsapp mainly for a provider called Karix should be be classified as 'WhatsApp', not 'Partner Integrations'
            
            - a new global control group feature is 'Campaign Management'. 
            
            - An AI feature to optimize email subject lines should be 'ML or AI', not 'Email'.

    ### OUTPUT FORMAT

        Structure your response EXACTLY as follows. Do not add any conversational text, introductions, or apologies.

            COMPETITOR: {competitor_name}

            PRODUCT_LINE: [The single most relevant product line from the list]

            FEATURE_UPDATE: [A short, descriptive title for the new feature or update]

            SUMMARY: [A 2-3 sentence summary explaining what the new feature does and its value to customers.]

            PM_ANALYSIS: [A 1-2 sentence analysis of the strategic implication for MoEngage. Consider whether this is a catch-up feature, an innovation, a threat to our market position, or an opportunity we can learn from.]

    ---

    ### INPUT TEXTS

    #### ARTICLE_TEXT

        {context}
    """
def get_final_ai_summary(full_context:str, competitor_name:str) -> dict:
    """A dispatcher that chooses the correct prompt and calls the AI in JSON mode."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "PASTE_YOUR_GEMINI_API_KEY_HERE":
        return {"error": "Gemini API Key not configured."}

    client = genai.Client(
        api_key=GEMINI_API_KEY,
    )
    if competitor_name == "Braze":
        prompt = get_braze_prompt(full_context, competitor_name)
    elif competitor_name == "Iterable":
        prompt = get_iterable_prompt(full_context, competitor_name)
    else:
        # Default to a generic prompt if competitor is unknown
        prompt = get_braze_prompt(full_context, competitor_name)
    print(f"\n printing prompt \n")
    print(f"{prompt}")
    print(f"\n" + "="*30 + "\n")
    model = "gemini-2.5-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt),
            ],
        ),
    ]
    try:
        response = client.models.generate_content(model=model, contents=contents,
                                              config={"response_mime_type": "application/json"})
        print(f"\n printing Response \n")
        print(f"{response}")
        try:
            # The AI might return a list with one item, or just the item itself.
            # This handles both cases.
            data = json.loads(response.text)
            if isinstance(data, list):
                return data[0] if data else {}
            return data
        except (json.JSONDecodeError, TypeError):
            print(f"--- WARNING: AI returned non-JSON text. Raw text below. ---")
            print(response.text)
            return {"error": "AI response was not valid JSON."}

    except Exception as e:
        print(f"ERROR: Could not get AI summary. Details: {e}")
        return {"error": f"Failed to get AI analysis: {e}"}


# --- COMPETITOR-SPECIFIC PARSERS ---

def parse_braze_page(url: str) -> list:
    print(f"  -> Parsing Braze (L1): {url}...")
    features_to_process = []
    l1_html = get_page_source_with_selenium(url)
    if not l1_html: return []
    soup = BeautifulSoup(l1_html, 'html.parser')
    guide_list = soup.find('div', id='guide_list')
    if not guide_list: return []
    monthly_links = [urllib.parse.urljoin(url, a['href']) for a in
                     guide_list.find_all('a', attrs={'data-navlink': True})]
    for month_url in monthly_links:
        print(f"    -> Parsing Braze month page (L2): {month_url}")
        month_html = get_page_source_with_selenium(month_url)
        if not month_html: continue
        try:
            month_soup = BeautifulSoup(month_html, 'html.parser')
            month_heading_tag = month_soup.find('h1')
            month_heading = month_heading_tag.get_text(strip=True) if month_heading_tag else "Unknown Month"
            article_container = month_soup.find('div', id='article-main')
            if not article_container: continue
            clean_html_content(article_container, [{"tag": "div", "id": "breadcrumb"}])
            for feature_heading in article_container.find_all('h3'):
                description_p = feature_heading.find_next_sibling('p')
                if description_p:
                    link_tag = description_p.find('a')
                    if link_tag and link_tag.get('href'):
                        final_url = urllib.parse.urljoin(month_url, link_tag.get('href'))
                        identifier = f"Braze - {month_heading} - {final_url}"
                        if not is_item_processed(identifier):
                            feature_name = feature_heading.get_text(strip=True)
                            print(f"      [NEW] Found Braze feature: {feature_name}")
                            short_desc = description_p.get_text(strip=True)
                            context = f"Feature: {feature_name}\n\nSummary: {short_desc}"
                            features_to_process.append(
                                {"identifier": identifier, "context": context, "source_url": final_url,
                                 "detail_links": [final_url], "competitor_name": "Braze"})
        except Exception as e:
            print(f"     ERROR processing Braze month page {month_url}. Details: {e}")
    return features_to_process


def parse_iterable_page(url: str) -> list:
    """
    A robust parser for Iterable that captures all paragraphs
    associated with a feature.
    """
    print(f"  -> Parsing Iterable page with multi-paragraph logic: {url}...")
    features = []
    html_content = get_page_source_with_selenium(url)
    if not html_content:
        return []

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # --- Simplified path to the content ---
        final_content_div = soup.select_one(
            "article.article section.article-info div.article-content div.article-body main.page div.theme-default-content"
        )

        if not final_content_div:
            print("     WARNING: Could not find the final content div.")
            return []

        # --- RE-INTEGRATED CLEANING LOGIC ---
        elements_to_remove = [
            {"tag": "div", "class": "table-of-contents"},
            {"tag": "div", "class": "article-footer"},
            {"tag": "div", "class": "article-votes"},
            {"tag": "div", "class": "article-more-questions"},
            {"tag": "div", "class": "article-return-to-top"},
            {"tag": "section", "class": "article-relatives"}
        ]
        clean_html_content(final_content_div, elements_to_remove)
        # --- END OF CLEANING LOGIC ---

        current_month_heading = ""
        # Find all H2 and H3 tags in their document order
        for heading in final_content_div.find_all(['h2', 'h3']):
            if heading.name == 'h2':
                current_month_heading = heading.get_text(strip=True)
                continue

            if heading.name == 'h3':
                if not current_month_heading:
                    continue

                month_identifier = f"Iterable - {current_month_heading}"
                feature_name = heading.get_text(strip=True)
                # Create the new combined identifier
                combined_identifier = f"{month_identifier} - {feature_name}"

                if is_item_processed(combined_identifier):
                    continue

                # --- NEW: Logic to capture ALL content until the next heading ---
                content_parts = []
                detail_links = []

                # Iterate through all siblings after the current H3
                for sibling in heading.find_next_siblings():
                    # Stop if we hit the next heading
                    if sibling.name in ['h2', 'h3']:
                        break

                    # Get the text from the element, regardless of its tag
                    # The ' ' separator provides better spacing for mixed content
                    text = sibling.get_text(separator=' ', strip=True)
                    if text:
                        content_parts.append(text)

                    # Also, extract any links if the sibling is a tag
                    if isinstance(sibling, Tag):
                        links = sibling.find_all('a', href=True)
                        for link in links:
                            absolute_link = urllib.parse.urljoin(url, link['href'])
                            detail_links.append(absolute_link)

                # --- END OF NEW LOGIC ---

                if content_parts:
                    # Join the collected text parts into a single description string
                    full_description = "\n".join(content_parts)

                    # Remove duplicate links while preserving order
                    unique_links = list(dict.fromkeys(detail_links))

                    primary_url = unique_links[-1] if unique_links else f"{url}#{feature_name.replace(' ','_').lower()}"

                    context = f"Month: {current_month_heading}\nFeature: {feature_name}\n\nSummary: {full_description}"

                    features.append({
                        "identifier": combined_identifier,
                        "context": context,
                        "source_url": primary_url,
                        "detail_links": unique_links,
                        "competitor_name": "Iterable"
                    })
        return features
    except Exception as e:
        print(f"     ERROR parsing Iterable page HTML. Details: {e}")
        return []

# --- WORKER FUNCTION FOR CONCURRENT PROCESSING (WITH DEBUG PRINTS) ---
def process_single_feature(feature: dict) -> dict:
    """
    Takes a feature dict, scrapes details, gets the AI summary, and returns the final data.
    This function is designed to be run in a separate thread.
    """
    print(f"--- Starting processing for: {feature['identifier']} ---")
    full_context = feature['context']

    if feature['competitor_name'] == 'Braze' and feature.get('detail_links'):
        deep_content = scrape_article_content(feature['detail_links'][0])
        full_context += "\n\n### DETAILED_ARTICLE \n\n" + deep_content

    # Restored print statement for context
    print(f"\n context is printed\n")
    print(f"{full_context}")
    print("\n"+"="*20 + "AI function to be called" + "="*10 + "\n")

    summary_data = get_final_ai_summary(full_context, feature['competitor_name'])

    # Restored print statement for raw summary_data
    print(f"\n printing summary_data\n")
    print(f"{summary_data} \n")
    print("="*20 + "Summary to be re-organised" + "="*10 + "\n")

    if "error" in summary_data:
        print(f"  -> AI Error for '{feature['identifier']}': {summary_data['error']}")
        return {"error": summary_data['error'], "identifier": feature['identifier']}

    summary_data['identifier'] = feature['identifier']
    summary_data['competitor'] = feature['competitor_name']
    summary_data['source_url'] = feature['source_url']

    # Restored print statement for reorganized summary_data
    print(f"\n Printing summary_data post re-organising\n")
    print(f"{summary_data} \n")
    print("=" * 20 + "Briefing_Body" + "=" * 10 + "\n")


    return summary_data

# --- MAIN SCRIPT LOGIC ---
if __name__ == "__main__":
    setup_database()
    competitors = {
        "Braze": {"url": "https://www.braze.com/docs/help/release_notes/2025", "parser": parse_braze_page}
        ,
         "Iterable": {"url": "https://support.iterable.com/hc/en-us/articles/33302033277332-2025-Release-Notes", "parser": parse_iterable_page}
    }
    all_new_features = []

    print("--- Starting AI Competition Scout ---")
    for name, config in competitors.items():
        print(f"\nProcessing competitor: {name}")
        features_from_parser = config["parser"](config["url"])
        all_new_features.extend(features_from_parser)

    print(f"\nPrinting All New Features:\n")
    print(f"{all_new_features}")

    if all_new_features:
        print(f"\n--- Found {len(all_new_features)} new features. Processing all with AI... ---")
        # =================================================================
        # REPLACEMENT CODE BLOCK - Use a simple loop instead of ThreadPool
        # =================================================================
        for feature in all_new_features:
            try:
                # Process one feature at a time
                summary_data = process_single_feature(feature)

                if "error" not in summary_data:
                    briefing_body = (
                        f"COMPETITOR: {summary_data.get('COMPETITOR', 'N/A')}\n"
                        f"PRODUCT_LINE: {summary_data.get('PRODUCT_LINE', 'N/A')}\n"
                        f"FEATURE_UPDATE: {summary_data.get('FEATURE_UPDATE', 'N/A')}\n"
                        f"SUMMARY: {summary_data.get('SUMMARY', 'N/A')}\n"
                        f"PM_ANALYSIS: {summary_data.get('PM_ANALYSIS', 'N/A')}\n"
                        f"source_url: {summary_data.get('source_url', 'N/A')}"
                    )
                    print("\n" + "=" * 20 + " INTELLIGENCE BRIEFING " + "=" * 20)
                    print(briefing_body)
                    print("=" * 65 + "\n")

                    add_briefing_to_db(summary_data)
                    print(f"      -> Briefing for identifier '{summary_data['identifier']}' saved to database.")

                    # --- RATE LIMIT DELAY ---
                    # To stay under 10 RPM, wait 6 seconds after each call (60 seconds / 10 = 6).
                    print("      -> Waiting 6 seconds to respect rate limit...")
                    time.sleep(6)
            except Exception as e:
                print(f"      ERROR: An unexpected exception occurred for feature '{feature['identifier']}': {e}")
    else:
        print("\nNo new features found during this run.")

    print("\n--- Scout finished run ---")