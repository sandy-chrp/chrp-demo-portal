// static/js/advanced_screenshot_detection.js
// ADVANCED DETECTION - Snipping Tool, Greenshot, etc.

(function() {
    'use strict';

    // ==========================================
    // 1. DETECT WINDOW FOCUS LOSS (Snipping Tool Opens)
    // ==========================================
    let focusLossCount = 0;
    let lastFocusLoss = 0;
    
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            const now = Date.now();
            const timeSinceLastLoss = now - lastFocusLoss;
            
            // If focus lost multiple times quickly (within 5 seconds)
            if (timeSinceLastLoss < 5000) {
                focusLossCount++;
                
                if (focusLossCount >= 2) {
                    // Likely screenshot tool
                    showScreenshotWarning();
                    blurContentTemporarily();
                    logToServer('focus_loss_screenshot', `Suspicious focus loss (${focusLossCount} times)`);
                }
            } else {
                focusLossCount = 1;
            }
            
            lastFocusLoss = now;
            
            // Always blur content when window loses focus
            blurContent();
        } else {
            // Restore content when focus returns
            unblurContent();
        }
    });

    // ==========================================
    // 2. DETECT WINDOW BLUR (Snipping Tool Activation)
    // ==========================================
    window.addEventListener('blur', function() {
        console.log('⚠️ Window blur detected - potential screenshot tool');
        blurContent();
        logToServer('window_blur', 'Window lost focus - screenshot tool suspected');
    });

    window.addEventListener('focus', function() {
        console.log('✓ Window focus restored');
        unblurContent();
    });

    // ==========================================
    // 3. MONITOR ACTIVE WINDOW TITLE CHANGES
    // ==========================================
    let lastTitle = document.title;
    
    setInterval(function() {
        if (document.title !== lastTitle) {
            console.log('📝 Title changed');
            lastTitle = document.title;
        }
    }, 500);

    // ==========================================
    // 4. DETECT SNIPPING TOOL SPECIFIC BEHAVIORS
    // ==========================================
    
    // Monitor mouse leaving window (snipping tool usage)
    let mouseLeftCount = 0;
    
    document.addEventListener('mouseleave', function(e) {
        // Only count if mouse left through top of window (common with snipping tool)
        if (e.clientY < 0) {
            mouseLeftCount++;
            
            if (mouseLeftCount > 2) {
                showScreenshotWarning();
                logToServer('mouse_leave_top', 'Mouse left top of window multiple times');
            }
        }
    });

    // ==========================================
    // 5. BLUR CONTENT FUNCTIONS
    // ==========================================
    function blurContent() {
        // Add blur overlay
        if (document.getElementById('screenshot-blur-overlay')) return;
        
        const overlay = document.createElement('div');
        overlay.id = 'screenshot-blur-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            z-index: 999997;
            display: flex;
            align-items: center;
            justify-content: center;
            pointer-events: none;
            transition: opacity 0.3s ease;
        `;
        
        overlay.innerHTML = `
            <div style="text-align: center; color: #1e3c72; font-size: 24px; font-weight: bold;">
                <i class="fas fa-shield-alt" style="font-size: 64px; margin-bottom: 20px; display: block;"></i>
                <div>Content Protected</div>
                <div style="font-size: 16px; margin-top: 10px; opacity: 0.7;">
                    Click to continue viewing
                </div>
            </div>
        `;
        
        document.body.appendChild(overlay);
    }

    function unblurContent() {
        const overlay = document.getElementById('screenshot-blur-overlay');
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.remove(), 300);
        }
    }

    function blurContentTemporarily() {
        blurContent();
        
        // Auto-remove after 3 seconds
        setTimeout(function() {
            if (!document.hidden) {
                unblurContent();
            }
        }, 3000);
    }

    // ==========================================
    // 6. SCREENSHOT WARNING
    // ==========================================
    function showScreenshotWarning() {
        const existing = document.getElementById('screenshot-warning-modal');
        if (existing) return;
        
        const modal = document.createElement('div');
        modal.id = 'screenshot-warning-modal';
        modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 999998;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: fadeIn 0.3s ease;
        `;
        
        modal.innerHTML = `
            <div style="background: white; padding: 40px; border-radius: 15px; max-width: 500px; text-align: center; box-shadow: 0 20px 60px rgba(0,0,0,0.4);">
                <i class="fas fa-exclamation-triangle" style="font-size: 64px; color: #ef4444; margin-bottom: 20px;"></i>
                <h2 style="color: #1e3c72; margin: 0 0 15px 0;">Screenshot Tool Detected</h2>
                <p style="color: #6b7280; margin: 0 0 20px 0; line-height: 1.6;">
                    We detected that you may be using a screenshot tool (like Snipping Tool or Greenshot). 
                    Screenshots are not allowed on this platform for security and content protection.
                </p>
                <p style="color: #ef4444; font-weight: 600; margin: 0 0 25px 0;">
                    This activity has been logged.
                </p>
                <button onclick="this.closest('div').parentElement.remove()" 
                        style="background: #1e3c72; color: white; border: none; padding: 12px 30px; border-radius: 8px; cursor: pointer; font-size: 16px; font-weight: 600;">
                    I Understand
                </button>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Auto-close after 8 seconds
        setTimeout(() => {
            if (modal.parentElement) {
                modal.style.opacity = '0';
                setTimeout(() => modal.remove(), 300);
            }
        }, 8000);
    }

    // ==========================================
    // 7. DETECT SCREEN CAPTURE APIS
    // ==========================================
    
    // Override navigator.mediaDevices.getDisplayMedia
    if (navigator.mediaDevices && navigator.mediaDevices.getDisplayMedia) {
        const originalGetDisplayMedia = navigator.mediaDevices.getDisplayMedia;
        
        navigator.mediaDevices.getDisplayMedia = function() {
            showScreenshotWarning();
            logToServer('screen_capture_api', 'getDisplayMedia API called');
            return Promise.reject(new Error('Screen capture not allowed'));
        };
    }

    // ==========================================
    // 8. MONITOR CLIPBOARD FOR IMAGES
    // ==========================================
    let clipboardCheckCount = 0;
    
    setInterval(async function() {
        try {
            const items = await navigator.clipboard.read();
            
            for (const item of items) {
                if (item.types.some(type => type.startsWith('image/'))) {
                    clipboardCheckCount++;
                    
                    // Clear clipboard
                    await navigator.clipboard.writeText('Screenshot not allowed on this platform');
                    
                    showScreenshotWarning();
                    logToServer('clipboard_image_detected', `Image found in clipboard (${clipboardCheckCount} times)`);
                    
                    // Flash screen
                    flashScreen();
                }
            }
        } catch (err) {
            // Permission denied or not supported
        }
    }, 2000); // Check every 2 seconds

    // ==========================================
    // 9. FLASH SCREEN EFFECT
    // ==========================================
    function flashScreen() {
        const flash = document.createElement('div');
        flash.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: white;
            z-index: 999996;
            pointer-events: none;
            animation: flashEffect 0.5s ease;
        `;
        
        document.body.appendChild(flash);
        
        setTimeout(() => flash.remove(), 500);
    }

    // ==========================================
    // 10. LOG TO SERVER
    // ==========================================
    function logToServer(type, description) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                         document.querySelector('[name=csrf-token]')?.content;
        
        if (!csrfToken) return;
        
        fetch('/customer/ajax/log-security-violation/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                violation_type: type,
                description: description,
                timestamp: new Date().toISOString(),
                page_url: window.location.href
            }),
            credentials: 'same-origin'
        }).catch(() => {});
    }

    // ==========================================
    // 11. ADD CSS ANIMATIONS
    // ==========================================
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes flashEffect {
            0% { opacity: 0; }
            25% { opacity: 1; }
            50% { opacity: 0; }
            75% { opacity: 1; }
            100% { opacity: 0; }
        }
    `;
    document.head.appendChild(style);

    console.log('%c🛡️ Advanced Screenshot Detection Active', 'color: #ef4444; font-size: 16px; font-weight: bold;');
    console.log('%c- Snipping Tool Detection', 'color: #6b7280; font-size: 12px;');
    console.log('%c- Window Blur Detection', 'color: #6b7280; font-size: 12px;');
    console.log('%c- Clipboard Monitoring', 'color: #6b7280; font-size: 12px;');

})();