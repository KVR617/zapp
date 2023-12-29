from features.core.settings import SCREENSHOT_MODE

OUTLINE = """
if (window.outlineElement) {
    window.outlineElement.style.cssText = window.outlineElement.style.cssText.replace(/outline: [A-z 0-9]+!important;/, '');
}
window.outlineElement = arguments[0];
window.outlineElement.style.cssText = window.outlineElement.style.cssText + '; outline: 2px fuchsia solid !important;'
window.outlineElement.scrollIntoView({
    block: "center"
});
""" if not SCREENSHOT_MODE else """
arguments[0].scrollIntoView({
    block: "center"
});
"""

OUTLINE_LIST = """
if (window.locatorElements) {
    window.locatorElements.forEach(function (locatorElement) {
        locatorElement.style.cssText = locatorElement.style.cssText.replace(/outline: [A-z 0-9]+!important;/, '');
    });
}
window.locatorElements = arguments[0];
window.locatorElements.forEach(function (locatorElement) {
    locatorElement.scrollIntoView({
        block: "center"
    });
    locatorElement.style.cssText = locatorElement.style.cssText + '; outline: 2px fuchsia solid !important;'
});
""" if not SCREENSHOT_MODE else ""

GET_TEXT = """
var locatorElement = arguments[0];
switch (locatorElement.nodeName.toLowerCase()) {
    case 'input':
    case 'textarea':
        return locatorElement.value;
    default:
        return locatorElement.innerText;
}
"""

TEXT_SEARCH = """
var elements = arguments[0];
var searchText = arguments[1];
var found = null;
elements.forEach(function (element) {
    if (element.innerText.trim().replace(/\s/g, ' ') === searchText.trim().replace(/\s/g, ' ')) {
        found = element;
    }
})
return found;
"""

FREEZE_ANIMATIONS = """
var styleText = '*, *:after, *:before {' +
'    transition-delay: 0s !important;' +
'    transition-duration: 0s !important;' +
'    animation-delay: -0.0001s !important;' +
'    animation-duration: 0s !important;' +
'    animation-play-state: paused !important;' +
'    caret-color: transparent !important;' +
'}';
var style = document.createElement('style');
style.type = 'text/css';
if (style.styleSheet) {
    style.styleSheet.cssText = styleText;
} else {
    style.appendChild(document.createTextNode(styleText));
}
document.getElementsByTagName('head')[0].appendChild(style);
"""

GET_PAGE_SCROLL_Y = """
return window.pageYOffset
"""

GET_PAGE_SCROLL_X = """
return window.pageXOffset
"""

SCROLL_ELEMENT_INTO_VIEW = """
var element = arguments[0]
element.scrollIntoView();
"""

CAS_LOGOUT = """
var xhr = new XMLHttpRequest();
xhr.open('GET', arguments[0]);
xhr.withCredentials = true;
xhr.send();
"""

CREATE_OVERLAY = """
var overlay = document.createElement('div');
overlay.style.opacity = 0;
overlay.style.position = 'fixed';
overlay.style.top = 0;
overlay.style.left = 0;
overlay.style.right = 0;
overlay.style.bottom = 0;
overlay.style.zIndex = 1000000;

window.zappAntiHoverOverlay = overlay;

document.body.appendChild(window.zappAntiHoverOverlay);
"""

REMOVE_OVERLAY = """
document.body.removeChild(window.zappAntiHoverOverlay)
"""
