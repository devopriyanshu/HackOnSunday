"""
Website Configuration for AI Browser Agent
Contains selectors and workflows for common websites
"""

SITE_CONFIGS = {
    # Google configurations
    "google.com": {
        "search_page": {
            "url_pattern": "https://www.google.com/search?*",
            "actions": {
                "search_box": {
                    "selector": "textarea[name='q']",
                    "fallbacks": ["[aria-label='Search']", "[title='Search']"]
                },
                "search_button": {
                    "selector": "input[value='Google Search']",
                    "fallbacks": ["button[type='submit']"]
                },
                "result_links": {
                    "selector": "div.g a",
                    "fallbacks": ["h3"]
                }
            },
            "workflows": {
                "search_and_open_first_result": [
                    {"action": "input", "target": "search_box", "value": "{query}"},
                    {"action": "click", "target": "search_button"},
                    {"action": "wait", "for": "result_links", "timeout": 5000},
                    {"action": "click", "target": "result_links", "index": 0}
                ]
            }
        }
    },
    
    # Amazon configurations
    "amazon.com": {
        "search_page": {
            "url_pattern": "https://www.amazon.com/s?*",
            "actions": {
                "search_box": {
                    "selector": "#twotabsearchtextbox",
                    "fallbacks": ["input[name='field-keywords']"]
                },
                "search_button": {
                    "selector": "#nav-search-submit-button",
                    "fallbacks": ["input.nav-input[type='submit']"]
                },
                "product_links": {
                    "selector": "div[data-component-type='s-search-result'] a.a-link-normal",
                    "fallbacks": ["h2 a"]
                }
            },
            "workflows": {
                "search_and_select_product": [
                    {"action": "input", "target": "search_box", "value": "{query}"},
                    {"action": "click", "target": "search_button"},
                    {"action": "wait", "for": "product_links", "timeout": 5000},
                    {"action": "click", "target": "product_links", "index": "{position}"}
                ]
            }
        },
        "product_page": {
            "url_pattern": "https://www.amazon.com/*/dp/*",
            "actions": {
                "add_to_cart": {
                    "selector": "#add-to-cart-button",
                    "fallbacks": ["#addToCart", "[data-action='add-to-cart']"]
                },
                "buy_now": {
                    "selector": "#buy-now-button",
                    "fallbacks": []
                }
            }
        },
        "login_page": {
            "url_pattern": "https://www.amazon.com/ap/signin*",
            "actions": {
                "email_field": {
                    "selector": "#ap_email",
                    "fallbacks": ["input[name='email']"]
                },
                "password_field": {
                    "selector": "#ap_password",
                    "fallbacks": ["input[name='password']"]
                },
                "signin_button": {
                    "selector": "#signInSubmit",
                    "fallbacks": ["input[type='submit']"]
                }
            }
        }
    },
    
    # GitHub configurations
    "github.com": {
        "login_page": {
            "url_pattern": "https://github.com/login*",
            "actions": {
                "username_field": {
                    "selector": "#login_field",
                    "fallbacks": ["input[name='login']"]
                },
                "password_field": {
                    "selector": "#password",
                    "fallbacks": ["input[name='password']"]
                },
                "signin_button": {
                    "selector": "input[name='commit']",
                    "fallbacks": ["[value='Sign in']"]
                }
            },
            "workflows": {
                "login": [
                    {"action": "input", "target": "username_field", "value": "{username}"},
                    {"action": "input", "target": "password_field", "value": "{password}"},
                    {"action": "click", "target": "signin_button"},
                    {"action": "wait", "for": "dashboard", "timeout": 5000}
                ]
            }
        },
        "repo_page": {
            "url_pattern": "https://github.com/*/*",
            "actions": {
                "clone_button": {
                    "selector": "get-repo",
                    "fallbacks": ["[data-testid='clone-button']"]
                },
                "issues_tab": {
                    "selector": "#issues-tab",
                    "fallbacks": ["a[href$='/issues']"]
                }
            }
        }
    },
    
    # Twitter configurations
    "twitter.com": {
        "login_page": {
            "url_pattern": "https://twitter.com/i/flow/login*",
            "actions": {
                "username_field": {
                    "selector": "input[autocomplete='username']",
                    "fallbacks": ["input[name='text']"]
                },
                "password_field": {
                    "selector": "input[autocomplete='current-password']",
                    "fallbacks": ["input[name='password']"]
                }
            }
        },
        "search_page": {
            "url_pattern": "https://twitter.com/search*",
            "actions": {
                "search_box": {
                    "selector": "input[data-testid='SearchBox_Search_Input']",
                    "fallbacks": ["[aria-label='Search query']"]
                }
            }
        }
    },
    
    # General purpose selectors
    "generic": {
        "common_elements": {
            "login_form": {
                "selectors": [
                    "form[action*='login']",
                    "form[id='login']",
                    "form[name='login']"
                ]
            },
            "search_box": {
                "selectors": [
                    "input[type='search']",
                    "[role='search'] input",
                    "input[name='q']"
                ]
            },
            "main_content": {
                "selectors": [
                    "main",
                    "#content",
                    ".main-content"
                ]
            }
        },
        "workflows": {
            "generic_login": [
                {"action": "find", "target": "username_field"},
                {"action": "input", "target": "username_field", "value": "{username}"},
                {"action": "find", "target": "password_field"},
                {"action": "input", "target": "password_field", "value": "{password}"},
                {"action": "find", "target": "submit_button"},
                {"action": "click", "target": "submit_button"}
            ]
        }
    }
}

# Helper functions
def get_site_config(url: str) -> dict:
    """
    Get configuration for a given URL
    """
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    
    # Remove subdomains (www, etc.)
    if domain.startswith('www.'):
        domain = domain[4:]
    
    return SITE_CONFIGS.get(domain, SITE_CONFIGS["generic"])

def get_element_selectors(site: str, page_type: str, element_name: str) -> list:
    """
    Get all possible selectors for an element
    """
    config = get_site_config(site)
    page_config = config.get(page_type, {})
    
    if not page_config:
        return []
    
    element_config = page_config.get("actions", {}).get(element_name, {})
    
    # Return main selector + fallbacks
    selectors = []
    if "selector" in element_config:
        selectors.append(element_config["selector"])
    if "fallbacks" in element_config:
        selectors.extend(element_config["fallbacks"])
    
    return selectors