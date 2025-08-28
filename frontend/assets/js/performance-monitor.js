// Performance Monitoring System for CIP Immobiliare Admin
class PerformanceMonitor {
    constructor() {
        this.metrics = {
            pageLoad: 0,
            domReady: 0,
            firstPaint: 0,
            firstContentfulPaint: 0,
            largestContentfulPaint: 0,
            cumulativeLayoutShift: 0,
            firstInputDelay: 0
        };
        
        this.init();
    }
    
    init() {
        // Measure page load time
        this.measurePageLoad();
        
        // Measure Core Web Vitals
        this.measureWebVitals();
        
        // Monitor console errors
        this.monitorConsoleErrors();
        
        // Check responsive design
        this.checkResponsiveDesign();
        
        // Report metrics after page load
        window.addEventListener('load', () => {
            setTimeout(() => this.reportMetrics(), 1000);
        });
    }
    
    measurePageLoad() {
        // Navigation Timing API
        window.addEventListener('load', () => {
            const navigation = performance.getEntriesByType('navigation')[0];
            
            this.metrics.pageLoad = navigation.loadEventEnd - navigation.fetchStart;
            this.metrics.domReady = navigation.domContentLoadedEventEnd - navigation.fetchStart;
            
            console.log('📊 Performance Metrics:');
            console.log(`🔄 Page Load: ${this.metrics.pageLoad}ms`);
            console.log(`📝 DOM Ready: ${this.metrics.domReady}ms`);
        });
    }
    
    measureWebVitals() {
        // First Paint
        const paintEntries = performance.getEntriesByType('paint');
        paintEntries.forEach(entry => {
            if (entry.name === 'first-paint') {
                this.metrics.firstPaint = entry.startTime;
            }
            if (entry.name === 'first-contentful-paint') {
                this.metrics.firstContentfulPaint = entry.startTime;
            }
        });
        
        // Largest Contentful Paint (Web Vitals)
        if ('PerformanceObserver' in window) {
            try {
                const lcpObserver = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    const lastEntry = entries[entries.length - 1];
                    this.metrics.largestContentfulPaint = lastEntry.startTime;
                });
                lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
            } catch (e) {
                console.warn('LCP measurement not supported');
            }
            
            // Cumulative Layout Shift
            try {
                const clsObserver = new PerformanceObserver((list) => {
                    let clsValue = 0;
                    for (const entry of list.getEntries()) {
                        if (!entry.hadRecentInput) {
                            clsValue += entry.value;
                        }
                    }
                    this.metrics.cumulativeLayoutShift = clsValue;
                });
                clsObserver.observe({ entryTypes: ['layout-shift'] });
            } catch (e) {
                console.warn('CLS measurement not supported');
            }
            
            // First Input Delay
            try {
                const fidObserver = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        this.metrics.firstInputDelay = entry.processingStart - entry.startTime;
                    }
                });
                fidObserver.observe({ entryTypes: ['first-input'] });
            } catch (e) {
                console.warn('FID measurement not supported');
            }
        }
    }
    
    monitorConsoleErrors() {
        const originalError = console.error;
        const originalWarn = console.warn;
        
        this.errorCount = 0;
        this.warningCount = 0;
        
        console.error = (...args) => {
            this.errorCount++;
            originalError.apply(console, args);
        };
        
        console.warn = (...args) => {
            this.warningCount++;
            originalWarn.apply(console, args);
        };
        
        // Monitor unhandled errors
        window.addEventListener('error', (event) => {
            this.errorCount++;
            console.error('Unhandled error:', event.error);
        });
        
        // Monitor unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.errorCount++;
            console.error('Unhandled promise rejection:', event.reason);
        });
    }
    
    checkResponsiveDesign() {
        // Check if viewport meta tag exists
        const viewportMeta = document.querySelector('meta[name="viewport"]');
        this.hasViewportMeta = !!viewportMeta;
        
        // Check if CSS Grid/Flexbox is used
        this.usesModernCSS = this.checkModernCSS();
        
        // Check mobile navigation
        this.hasMobileNav = !!document.querySelector('[data-mobile-nav], .mobile-nav, #mobile-nav');
    }
    
    checkModernCSS() {
        const stylesheets = Array.from(document.styleSheets);
        let hasGridOrFlex = false;
        
        try {
            stylesheets.forEach(sheet => {
                if (sheet.cssRules) {
                    Array.from(sheet.cssRules).forEach(rule => {
                        if (rule.style) {
                            const cssText = rule.style.cssText.toLowerCase();
                            if (cssText.includes('grid') || cssText.includes('flex')) {
                                hasGridOrFlex = true;
                            }
                        }
                    });
                }
            });
        } catch (e) {
            // Cross-origin stylesheets might throw errors
        }
        
        return hasGridOrFlex;
    }
    
    reportMetrics() {
        const report = {
            timestamp: new Date().toISOString(),
            url: window.location.href,
            userAgent: navigator.userAgent,
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight
            },
            performance: this.metrics,
            quality: {
                errors: this.errorCount,
                warnings: this.warningCount,
                hasViewportMeta: this.hasViewportMeta,
                usesModernCSS: this.usesModernCSS,
                hasMobileNav: this.hasMobileNav
            },
            scores: this.calculateScores()
        };
        
        console.log('📊 Performance Report:', report);
        
        // Send to admin dashboard if available
        this.sendToAdminDashboard(report);
        
        return report;
    }
    
    calculateScores() {
        const scores = {};
        
        // Page Load Score (< 3 seconds = 100%)
        scores.pageLoad = Math.max(0, 100 - (this.metrics.pageLoad - 3000) / 30);
        scores.pageLoad = Math.min(100, Math.max(0, scores.pageLoad));
        
        // LCP Score (< 2.5s = Good)
        if (this.metrics.largestContentfulPaint > 0) {
            scores.lcp = this.metrics.largestContentfulPaint <= 2500 ? 100 : 
                        this.metrics.largestContentfulPaint <= 4000 ? 75 : 25;
        }
        
        // CLS Score (< 0.1 = Good)
        if (this.metrics.cumulativeLayoutShift >= 0) {
            scores.cls = this.metrics.cumulativeLayoutShift <= 0.1 ? 100 :
                       this.metrics.cumulativeLayoutShift <= 0.25 ? 75 : 25;
        }
        
        // FID Score (< 100ms = Good)
        if (this.metrics.firstInputDelay > 0) {
            scores.fid = this.metrics.firstInputDelay <= 100 ? 100 :
                        this.metrics.firstInputDelay <= 300 ? 75 : 25;
        }
        
        // Console Errors Score
        scores.errors = this.errorCount === 0 ? 100 : Math.max(0, 100 - this.errorCount * 10);
        
        // Responsive Design Score
        scores.responsive = 0;
        if (this.hasViewportMeta) scores.responsive += 25;
        if (this.usesModernCSS) scores.responsive += 25;
        if (this.hasMobileNav) scores.responsive += 25;
        scores.responsive += 25; // Base score for existing
        
        // Overall Lighthouse-style score
        const weights = {
            pageLoad: 0.25,
            lcp: 0.25,
            cls: 0.15,
            fid: 0.15,
            errors: 0.10,
            responsive: 0.10
        };
        
        let overallScore = 0;
        Object.keys(weights).forEach(metric => {
            if (scores[metric] !== undefined) {
                overallScore += scores[metric] * weights[metric];
            }
        });
        
        scores.overall = Math.round(overallScore);
        
        return scores;
    }
    
    sendToAdminDashboard(report) {
        // Send performance data to admin endpoint if available
        if (window.location.pathname.includes('/admin/')) {
            fetch('/admin/performance/report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(report)
            }).catch(error => {
                console.warn('Could not send performance report:', error);
            });
        }
    }
    
    // Public methods for manual testing
    getMetrics() {
        return this.metrics;
    }
    
    getScores() {
        return this.calculateScores();
    }
    
    generateLighthouseReport() {
        const scores = this.calculateScores();
        
        console.log('\n🚦 Lighthouse-style Report:');
        console.log(`📊 Overall Score: ${scores.overall}/100`);
        console.log(`⚡ Performance: ${Math.round(scores.pageLoad)}/100`);
        console.log(`🎨 Best Practices: ${scores.errors}/100`);
        console.log(`📱 Responsive: ${scores.responsive}/100`);
        
        if (scores.lcp) console.log(`🖼️ LCP: ${Math.round(scores.lcp)}/100`);
        if (scores.cls) console.log(`📐 CLS: ${Math.round(scores.cls)}/100`);
        if (scores.fid) console.log(`⚡ FID: ${Math.round(scores.fid)}/100`);
        
        return scores;
    }
}

// Accessibility Checker
class AccessibilityChecker {
    constructor() {
        this.issues = [];
        this.init();
    }
    
    init() {
        window.addEventListener('load', () => {
            setTimeout(() => this.runAccessibilityCheck(), 500);
        });
    }
    
    runAccessibilityCheck() {
        this.issues = [];
        
        // Check for missing alt attributes on images
        this.checkImageAlt();
        
        // Check for proper heading hierarchy
        this.checkHeadingHierarchy();
        
        // Check for form labels
        this.checkFormLabels();
        
        // Check for color contrast (basic check)
        this.checkColorContrast();
        
        // Check for keyboard navigation
        this.checkKeyboardNavigation();
        
        // Check for ARIA attributes
        this.checkARIAAttributes();
        
        this.reportAccessibility();
    }
    
    checkImageAlt() {
        const images = document.querySelectorAll('img');
        images.forEach((img, index) => {
            if (!img.hasAttribute('alt') || img.getAttribute('alt').trim() === '') {
                this.issues.push({
                    type: 'missing-alt',
                    severity: 'error',
                    message: `Image ${index + 1} missing alt attribute`,
                    element: img
                });
            }
        });
    }
    
    checkHeadingHierarchy() {
        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        let previousLevel = 0;
        
        headings.forEach(heading => {
            const currentLevel = parseInt(heading.tagName.charAt(1));
            
            if (currentLevel > previousLevel + 1) {
                this.issues.push({
                    type: 'heading-hierarchy',
                    severity: 'warning',
                    message: `Heading level skipped: ${heading.tagName} after h${previousLevel}`,
                    element: heading
                });
            }
            
            previousLevel = currentLevel;
        });
    }
    
    checkFormLabels() {
        const inputs = document.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            const id = input.getAttribute('id');
            const label = id ? document.querySelector(`label[for="${id}"]`) : null;
            const ariaLabel = input.getAttribute('aria-label');
            const ariaLabelledby = input.getAttribute('aria-labelledby');
            
            if (!label && !ariaLabel && !ariaLabelledby) {
                this.issues.push({
                    type: 'missing-label',
                    severity: 'error',
                    message: 'Form input missing label or aria-label',
                    element: input
                });
            }
        });
    }
    
    checkColorContrast() {
        // Basic color contrast check (simplified)
        const textElements = document.querySelectorAll('p, span, div, a, button, label');
        let lowContrastCount = 0;
        
        textElements.forEach(element => {
            const styles = window.getComputedStyle(element);
            const color = styles.color;
            const backgroundColor = styles.backgroundColor;
            
            // Simple check for very light gray text (potential contrast issue)
            if (color.includes('rgb(156') || color.includes('rgb(209') || color.includes('#ccc') || color.includes('#ddd')) {
                lowContrastCount++;
            }
        });
        
        if (lowContrastCount > 10) {
            this.issues.push({
                type: 'low-contrast',
                severity: 'warning',
                message: `Potential low contrast text detected (${lowContrastCount} elements)`,
                element: null
            });
        }
    }
    
    checkKeyboardNavigation() {
        const interactiveElements = document.querySelectorAll('button, a, input, select, textarea, [tabindex]');
        let missingTabIndexCount = 0;
        
        interactiveElements.forEach(element => {
            const tabIndex = element.getAttribute('tabindex');
            
            // Check for negative tabindex (removes from tab order)
            if (tabIndex === '-1' && element.tagName !== 'DIV') {
                this.issues.push({
                    type: 'keyboard-navigation',
                    severity: 'warning',
                    message: 'Interactive element removed from tab order',
                    element: element
                });
            }
        });
    }
    
    checkARIAAttributes() {
        // Check for buttons without proper ARIA
        const buttons = document.querySelectorAll('button');
        buttons.forEach(button => {
            const hasAriaLabel = button.hasAttribute('aria-label');
            const hasAriaLabelledby = button.hasAttribute('aria-labelledby');
            const hasTextContent = button.textContent.trim().length > 0;
            
            if (!hasAriaLabel && !hasAriaLabelledby && !hasTextContent) {
                this.issues.push({
                    type: 'missing-aria',
                    severity: 'error',
                    message: 'Button without accessible name',
                    element: button
                });
            }
        });
        
        // Check for form controls without proper ARIA
        const formControls = document.querySelectorAll('[role="button"], [role="checkbox"], [role="radio"]');
        formControls.forEach(control => {
            if (!control.hasAttribute('aria-label') && !control.hasAttribute('aria-labelledby')) {
                this.issues.push({
                    type: 'missing-aria',
                    severity: 'warning',
                    message: 'ARIA control without accessible name',
                    element: control
                });
            }
        });
    }
    
    reportAccessibility() {
        const errorCount = this.issues.filter(issue => issue.severity === 'error').length;
        const warningCount = this.issues.filter(issue => issue.severity === 'warning').length;
        
        console.log('\n♿ Accessibility Report:');
        console.log(`❌ Errors: ${errorCount}`);
        console.log(`⚠️ Warnings: ${warningCount}`);
        
        if (this.issues.length === 0) {
            console.log('✅ No accessibility issues detected!');
        } else {
            console.log('📋 Issues found:');
            this.issues.forEach((issue, index) => {
                console.log(`${index + 1}. [${issue.severity.toUpperCase()}] ${issue.message}`);
            });
        }
        
        // Calculate WCAG compliance score
        const maxScore = 100;
        const errorPenalty = errorCount * 15;
        const warningPenalty = warningCount * 5;
        const score = Math.max(0, maxScore - errorPenalty - warningPenalty);
        
        console.log(`📊 WCAG 2.1 Compliance Score: ${score}/100`);
        
        return {
            score,
            errors: errorCount,
            warnings: warningCount,
            issues: this.issues
        };
    }
    
    getAccessibilityReport() {
        return this.reportAccessibility();
    }
}

// Mobile Performance Checker
class MobilePerformanceChecker {
    constructor() {
        this.isMobile = this.detectMobile();
        this.touchSupported = 'ontouchstart' in window;
        
        if (this.isMobile) {
            this.init();
        }
    }
    
    detectMobile() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
               window.innerWidth <= 768;
    }
    
    init() {
        this.checkTouchTargets();
        this.checkScrollPerformance();
        this.checkViewportSettings();
        this.reportMobileMetrics();
    }
    
    checkTouchTargets() {
        const interactiveElements = document.querySelectorAll('button, a, input, select');
        let smallTargetsCount = 0;
        
        interactiveElements.forEach(element => {
            const rect = element.getBoundingClientRect();
            const minSize = 44; // Apple's recommended minimum touch target size
            
            if (rect.width < minSize || rect.height < minSize) {
                smallTargetsCount++;
            }
        });
        
        this.smallTargetsCount = smallTargetsCount;
    }
    
    checkScrollPerformance() {
        let scrollStart = performance.now();
        let scrollSamples = [];
        
        const scrollHandler = () => {
            const now = performance.now();
            scrollSamples.push(now - scrollStart);
            scrollStart = now;
            
            if (scrollSamples.length > 10) {
                window.removeEventListener('scroll', scrollHandler);
                
                const avgScrollTime = scrollSamples.reduce((a, b) => a + b, 0) / scrollSamples.length;
                this.avgScrollTime = avgScrollTime;
                
                console.log(`📱 Mobile Scroll Performance: ${avgScrollTime.toFixed(2)}ms avg`);
            }
        };
        
        window.addEventListener('scroll', scrollHandler, { passive: true });
        
        // Trigger a small scroll to test
        setTimeout(() => {
            window.scrollBy(0, 1);
            setTimeout(() => window.scrollBy(0, -1), 100);
        }, 1000);
    }
    
    checkViewportSettings() {
        const viewport = document.querySelector('meta[name="viewport"]');
        this.hasProperViewport = viewport && 
                                viewport.content.includes('width=device-width') &&
                                viewport.content.includes('initial-scale=1');
    }
    
    reportMobileMetrics() {
        setTimeout(() => {
            console.log('\n📱 Mobile Performance Report:');
            console.log(`📱 Device: ${this.isMobile ? 'Mobile' : 'Desktop'}`);
            console.log(`👆 Touch Support: ${this.touchSupported ? 'Yes' : 'No'}`);
            console.log(`🎯 Small Touch Targets: ${this.smallTargetsCount || 0}`);
            console.log(`📐 Proper Viewport: ${this.hasProperViewport ? 'Yes' : 'No'}`);
            if (this.avgScrollTime) {
                console.log(`🔄 Avg Scroll Time: ${this.avgScrollTime.toFixed(2)}ms`);
            }
            
            const mobileScore = this.calculateMobileScore();
            console.log(`📊 Mobile Score: ${mobileScore}/100`);
        }, 2000);
    }
    
    calculateMobileScore() {
        let score = 100;
        
        if (!this.hasProperViewport) score -= 20;
        if (this.smallTargetsCount > 5) score -= 15;
        if (this.avgScrollTime && this.avgScrollTime > 16) score -= 10; // 60fps = 16ms
        if (!this.touchSupported && this.isMobile) score -= 10;
        
        return Math.max(0, score);
    }
}

// Initialize performance monitoring
let performanceMonitor;
let accessibilityChecker;
let mobilePerformanceChecker;

document.addEventListener('DOMContentLoaded', function() {
    // Only run in admin pages to avoid affecting user experience
    if (window.location.pathname.includes('/admin/')) {
        performanceMonitor = new PerformanceMonitor();
        accessibilityChecker = new AccessibilityChecker();
        mobilePerformanceChecker = new MobilePerformanceChecker();
        
        // Add global functions for manual testing
        window.getPerformanceReport = () => performanceMonitor.reportMetrics();
        window.getAccessibilityReport = () => accessibilityChecker.getAccessibilityReport();
        window.generateLighthouseReport = () => performanceMonitor.generateLighthouseReport();
    }
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PerformanceMonitor, AccessibilityChecker, MobilePerformanceChecker };
}
