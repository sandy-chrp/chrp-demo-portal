// static/js/customer_security_warning_only.js
// FINAL FIX - CSRF Token Fixed + Navigation Allowed

(function() {
    'use strict';

    // ==========================================
    // CRITICAL: Get CSRF Token Properly
    // ==========================================
    function getCSRFToken() {
        // Method 1: From meta tag
        let token = document.querySelector('[name=csrf-token]')?.content;
        
        // Method 2: From form input
        if (!token) {
            token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        }
        
        // Method 3: From cookie
        if (!token) {
            const cookieValue = document.cookie
                .split('; ')
                .find(row => row.startsWith('csrftoken='));
            if (cookieValue) {
                token = cookieValue.split('=')[1];
            }
        }
        
        console.log('🔑 CSRF Token:', token ? 'Found' : 'NOT FOUND');
        return token;
    }

    // ==========================================
    // CRITICAL: Exempt Navigation Elements
    // ==========================================
    const EXEMPTED_SELECTORS = [
        '.customer-sidebar',
        '.sidebar-nav',
        '.nav-link',
        '.nav-item',
        '.customer-header',
        '.dropdown-menu',
        'a[href^="/customer/"]',
        'a[href^="/accounts/"]',
        'button[data-bs-toggle]',
        '.btn',
        '.dropdown-toggle',
        'form'
    ];

    function isExemptedElement(element) {
        if (!element) return false;
        
        for (const selector of EXEMPTED_SELECTORS) {
            try {
                if (element.matches && element.matches(selector)) {
                    return true;
                }
                if (element.closest && element.closest(selector)) {
                    return true;
                }
            } catch (e) {
                continue;
            }
        }
        return false;
    }

    // ==========================================
    // 1. RIGHT CLICK PROTECTION
    // ==========================================
    document.addEventListener('contextmenu', function(e) {
        // Always allow on navigation
        if (isExemptedElement(e.target)) {
            return true;
        }
        
        // Allow on form elements
        const formElements = ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON'];
        if (formElements.includes(e.target.tagName)) {
            return true;
        }
        
        e.preventDefault();
        showWarning('Right-click is disabled for content protection');
        
        // Only log if not on navigation (reduce spam)
        if (!e.target.closest('.customer-sidebar, .customer-header')) {
            logActivity('right_click_attempt', 'Right-click on content');
        }
        
        return false;
    });

    // ==========================================
    // 2. KEYBOARD SHORTCUTS
    // ==========================================
    document.addEventListener('keydown', function(e) {
        // Don't block if on exempted element
        if (isExemptedElement(document.activeElement)) {
            return true;
        }
        
        let shouldBlock = false;
        let message = '';

        if (e.key === 'F12') {
            shouldBlock = true;
            message = 'Developer tools are not allowed';
        } else if (e.ctrlKey && e.shiftKey && e.key === 'I') {
            shouldBlock = true;
            message = 'Developer tools are not allowed';
        } else if (e.ctrlKey && e.shiftKey && e.key === 'J') {
            shouldBlock = true;
            message = 'Console is not allowed';
        } else if (e.ctrlKey && e.shiftKey && e.key === 'C') {
            shouldBlock = true;
            message = 'Inspect element is not allowed';
        } else if (e.ctrlKey && e.key === 'u') {
            shouldBlock = true;
            message = 'View source is not allowed';
        } else if (e.ctrlKey && e.key === 's') {
            shouldBlock = true;
            message = 'Saving page is not allowed';
        } else if (e.ctrlKey && e.key === 'p') {
            shouldBlock = true;
            message = 'Printing is not allowed';
        }

        if (shouldBlock) {
            e.preventDefault();
            showWarning(message);
            return false;
        }
    });

    // ==========================================
    // 3. PRINT SCREEN DETECTION
    // ==========================================
    document.addEventListener('keyup', function(e) {
        if (e.key === 'PrintScreen' || e.keyCode === 44) {
            navigator.clipboard.writeText('Screenshot not allowed').catch(() => {});
            showWarning('Screenshots are not allowed');
            logActivity('screenshot_attempt', 'PrintScreen detected');
        }
    });

    // ==========================================
    // 4. PREVENT TEXT SELECTION (Content Only)
    // ==========================================
    document.addEventListener('selectstart', function(e) {
        if (isExemptedElement(e.target)) {
            return true;
        }
        
        const formElements = ['INPUT', 'TEXTAREA', 'SELECT'];
        if (formElements.includes(e.target.tagName)) {
            return true;
        }
        
        const protectedAreas = e.target.closest('.demo-card, .customer-card, .demo-description');
        if (protectedAreas) {
            e.preventDefault();
            return false;
        }
    });

    // ==========================================
    // 5. PREVENT COPY
    // ==========================================
    document.addEventListener('copy', function(e) {
        if (isExemptedElement(document.activeElement)) {
            return true;
        }
        
        const formElements = ['INPUT', 'TEXTAREA', 'SELECT'];
        if (formElements.includes(document.activeElement.tagName)) {
            return true;
        }
        
        const selection = window.getSelection().toString();
        if (selection.length > 0) {
            e.preventDefault();
            navigator.clipboard.writeText('').catch(() => {});
            showWarning('Copying content is not allowed');
            return false;
        }
    });

    // ==========================================
    // 6. PREVENT DRAG (Media Only)
    // ==========================================
    document.addEventListener('dragstart', function(e) {
        if (e.target.tagName === 'IMG' || e.target.tagName === 'VIDEO') {
            e.preventDefault();
            showWarning('Dragging media is not allowed');
            return false;
        }
    });

    // ==========================================
    // 7. VIDEO PROTECTION
    // ==========================================
    function protectVideos() {
        document.querySelectorAll('video').forEach(function(video) {
            video.controlsList = 'nodownload noplaybackrate';
            video.disablePictureInPicture = true;
            
            video.addEventListener('contextmenu', function(e) {
                e.preventDefault();
                e.stopPropagation();
                showWarning('Right-click on video is not allowed');
                return false;
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', protectVideos);
    } else {
        protectVideos();
    }

    const observer = new MutationObserver(protectVideos);
    observer.observe(document.body, { childList: true, subtree: true });

    // ==========================================
    // 8. SHOW WARNING POPUP
    // ==========================================
    function showWarning(message) {
        const existing = document.getElementById('security-warning-toast');
        if (existing) existing.remove();
        
        const toast = document.createElement('div');
        toast.id = 'security-warning-toast';
        toast.innerHTML = `
            <i class="fas fa-shield-alt me-2"></i>
            <span>${message}</span>
        `;
        toast.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
            padding: 15px 25px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            z-index: 999999;
            display: flex;
            align-items: center;
            font-weight: 500;
            font-size: 14px;
            max-width: 400px;
            transition: all 0.3s ease;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(function() {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(400px)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ==========================================
    // 9. LOG ACTIVITY (WITH PROPER ERROR HANDLING)
    // ==========================================
    let logQueue = [];
    let isLogging = false;

    function logActivity(activityType, description) {
        // Add to queue
        logQueue.push({ activityType, description, timestamp: Date.now() });
        
        // Process queue if not already processing
        if (!isLogging) {
            processLogQueue();
        }
    }

    function processLogQueue() {
        if (logQueue.length === 0) {
            isLogging = false;
            return;
        }
        
        isLogging = true;
        const item = logQueue.shift();
        
        // Debounce - only log if last log was > 2 seconds ago
        const now = Date.now();
        if (window.lastLogTime && (now - window.lastLogTime) < 2000) {
            console.log('⏸️ Skipping log (debounce)');
            setTimeout(processLogQueue, 100);
            return;
        }
        
        window.lastLogTime = now;
        
        const csrfToken = getCSRFToken();
        
        if (!csrfToken) {
            console.warn('⚠️ CSRF token not found - skipping log');
            setTimeout(processLogQueue, 100);
            return;
        }
        
        const payload = {
            violation_type: item.activityType,
            description: item.description,
            timestamp: new Date(item.timestamp).toISOString(),
            page_url: window.location.href
        };
        
        console.log('📤 Logging activity:', payload);
        
        fetch('/customer/ajax/log-security-violation/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(payload),
            credentials: 'same-origin'
        })
        .then(response => {
            console.log('📥 Response status:', response.status);
            if (!response.ok) {
                return response.text().then(text => {
                    console.error('❌ Server error:', text);
                    throw new Error(`HTTP ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('✅ Activity logged:', data);
        })
        .catch(error => {
            console.warn('⚠️ Logging failed:', error);
        })
        .finally(() => {
            setTimeout(processLogQueue, 100);
        });
    }

    // ==========================================
    // 10. ADD CSS STYLES
    // ==========================================
    const style = document.createElement('style');
    style.textContent = `
        /* Allow selection on navigation */
        .customer-sidebar,
        .sidebar-nav,
        .nav-link,
        .customer-header,
        .dropdown-menu {
            -webkit-user-select: text !important;
            -moz-user-select: text !important;
            user-select: text !important;
        }

        /* Prevent selection on content only */
        .customer-content .demo-card,
        .customer-content .customer-card,
        .demo-description {
            -webkit-user-select: none;
            -moz-user-select: none;
            user-select: none;
        }

        /* Allow selection in inputs */
        input, textarea, select {
            -webkit-user-select: text !important;
            -moz-user-select: text !important;
            user-select: text !important;
        }

        /* Prevent image dragging */
        img {
            -webkit-user-drag: none;
            user-drag: none;
        }

        /* Navigation images should be draggable */
        .customer-sidebar img,
        .customer-header img {
            -webkit-user-drag: auto;
            user-drag: auto;
        }

        /* Video protection */
        video::-webkit-media-controls-download-button {
            display: none !important;
        }
    `;
    document.head.appendChild(style);

    console.log('%c✓ Security Active - Logging Enabled', 'color: #10b981; font-size: 14px; font-weight: bold;');

})();