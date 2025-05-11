/**
 * 华为鸿蒙系统优化脚本
 * HarmonyOS Optimization Script
 */

document.addEventListener('DOMContentLoaded', function() {
    // 检测是否是鸿蒙系统
    const isHarmonyOS = /HarmonyOS|EMUI|HUAWEI|HiSilicon/i.test(navigator.userAgent);
    
    if (isHarmonyOS) {
        document.documentElement.classList.add('harmony-os');
    }
    
    // 修复移动端100vh问题
    function setHeight() {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    }
    
    // 初始设置和监听窗口大小变化
    setHeight();
    window.addEventListener('resize', setHeight);
    
    // 修复触摸滚动问题
    const scrollElements = document.querySelectorAll('.table-responsive, .nav-tabs');
    scrollElements.forEach(element => {
        element.addEventListener('touchstart', function(e) {
            if (this.scrollWidth > this.clientWidth) {
                e.stopPropagation();
            }
        }, { passive: true });
    });
    
    // 延迟加载非关键资源
    function lazyLoadResources() {
        // 预加载图片
        const images = document.querySelectorAll('img[data-src]');
        images.forEach(img => {
            if (img.dataset.src) {
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
            }
        });
    }
    
    // 页面完全加载后执行
    window.addEventListener('load', lazyLoadResources);
    
    // 优化表单提交，防止重复提交
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitButtons = this.querySelectorAll('button[type="submit"], input[type="submit"]');
            submitButtons.forEach(button => {
                button.disabled = true;
                if (button.tagName === 'BUTTON') {
                    button.innerHTML = '处理中...';
                } else {
                    button.value = '处理中...';
                }
            });
        });
    });
    
    // 检测网络状态变化
    window.addEventListener('online', function() {
        document.body.classList.remove('offline');
    });
    
    window.addEventListener('offline', function() {
        document.body.classList.add('offline');
    });
}); 