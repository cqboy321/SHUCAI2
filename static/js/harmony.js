/**
 * 华为鸿蒙系统优化脚本
 * HarmonyOS Optimization Script
 */

// 立即执行的初始化函数，确保在DOM内容加载前准备好
(function() {
    // 预设置导航菜单默认为折叠状态
    if (window.localStorage.getItem('navbarExpanded') === 'true') {
        window.localStorage.setItem('navbarExpanded', 'false');
    }
})();

document.addEventListener('DOMContentLoaded', function() {
    // 检测是否是鸿蒙系统
    const isHarmonyOS = /HarmonyOS|EMUI|HUAWEI|HiSilicon/i.test(navigator.userAgent);
    
    if (isHarmonyOS) {
        document.documentElement.classList.add('harmony-os');
        document.body.classList.add('harmony-os');
    }
    
    // 检测是否是移动设备
    const isMobile = window.innerWidth < 769 || /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile/i.test(navigator.userAgent);
    
    if (isMobile) {
        document.documentElement.classList.add('mobile-device');
        document.body.classList.add('mobile-device');
    }
    
    // 确保导航栏始终固定在顶部
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        // 强制设置导航栏始终固定在顶部
        navbar.style.position = 'fixed';
        navbar.style.top = 'env(safe-area-inset-top, 0px)';
        navbar.style.transform = 'translateY(0)';
        navbar.style.transition = 'none';
        
        // 处理自定义导航菜单
        const navbarToggler = document.getElementById('navbarToggler');
        const navbarMenu = document.getElementById('navbarMenu');
        
        if (navbarToggler && navbarMenu && isMobile) {
            // 确保初始状态下菜单是隐藏的
            navbarMenu.style.display = 'none';
            
            console.log('Custom mobile menu initialized');
            
            // 点击菜单按钮时处理菜单显示/隐藏
            navbarToggler.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                if (navbarMenu.style.display === 'none' || navbarMenu.style.display === '') {
                    // 显示菜单
                    navbarMenu.style.display = 'block';
                    navbarToggler.classList.remove('collapsed');
                    
                    // 点击菜单外部区域隐藏菜单
                    const closeMenu = function(e) {
                        if (!navbarMenu.contains(e.target) && !navbarToggler.contains(e.target)) {
                            navbarMenu.style.display = 'none';
                            navbarToggler.classList.add('collapsed');
                            document.removeEventListener('click', closeMenu);
                        }
                    };
                    
                    // 延迟添加点击事件监听
                    setTimeout(() => {
                        document.addEventListener('click', closeMenu);
                    }, 10);
                } else {
                    // 隐藏菜单
                    navbarMenu.style.display = 'none';
                    navbarToggler.classList.add('collapsed');
                }
            });
            
            // 处理菜单中的下拉选项
            const dropdownToggle = navbarMenu.querySelector('.dropdown-toggle');
            const dropdownMenu = navbarMenu.querySelector('.dropdown-menu');
            
            if (dropdownToggle && dropdownMenu) {
                dropdownToggle.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    if (dropdownMenu.style.display === 'none' || dropdownMenu.style.display === '') {
                        dropdownMenu.style.display = 'block';
                    } else {
                        dropdownMenu.style.display = 'none';
                    }
                });
            }
            
            // 点击菜单项时隐藏菜单
            const navLinks = navbarMenu.querySelectorAll('.nav-link:not(.dropdown-toggle)');
            navLinks.forEach(link => {
                link.addEventListener('click', function() {
                    navbarMenu.style.display = 'none';
                    navbarToggler.classList.add('collapsed');
                    
                    // 添加点击反馈
                    this.style.backgroundColor = 'rgba(255,255,255,0.2)';
                    setTimeout(() => {
                        this.style.backgroundColor = '';
                    }, 200);
                });
            });
        }
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
    
    // ===== 导航和交互优化 =====
    
    // 修复下拉菜单在鸿蒙系统中的显示问题
    function enhanceDropdowns() {
        const dropdownToggles = document.querySelectorAll('.dropdown-toggle');
        
        // 为每个下拉菜单添加增强
        dropdownToggles.forEach(toggle => {
            // 获取相关的下拉菜单
            const dropdownMenu = toggle.nextElementSibling;
            if (!dropdownMenu || !dropdownMenu.classList.contains('dropdown-menu')) return;
            
            // 强制应用z-index以确保菜单在最前层
            dropdownMenu.style.zIndex = '99999';
            
            // 使用Bootstrap的事件处理菜单显示
            toggle.addEventListener('shown.bs.dropdown', function () {
                // 确保菜单显示
                dropdownMenu.classList.add('show');
                dropdownMenu.style.display = 'block';
                dropdownMenu.style.opacity = '1';
                dropdownMenu.style.visibility = 'visible';
                
                // 固定菜单位置（在移动设备上）
                if (isMobile) {
                    dropdownMenu.style.position = 'fixed';
                    
                    // 计算正确的顶部位置
                    const navbarHeight = document.querySelector('.navbar').offsetHeight;
                    const safeAreaTop = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--safe-area-inset-top'));
                    dropdownMenu.style.top = (navbarHeight + safeAreaTop) + 'px';
                    
                    // 设置右侧位置
                    dropdownMenu.style.right = '5px';
                    dropdownMenu.style.left = 'auto';
                }
            });
            
            // 防止菜单被点击后立即消失
            dropdownMenu.addEventListener('click', function(e) {
                // 如果点击的是菜单项，不要立即关闭菜单
                if (e.target.classList.contains('dropdown-item')) {
                    e.stopPropagation();
                    
                    // 给菜单项一点时间的视觉反馈后再关闭菜单
                    setTimeout(() => {
                        // 如果菜单项不是导航链接，则手动关闭菜单
                        if (!e.target.getAttribute('href')) {
                            toggle.click();
                        }
                    }, 100);
                }
            });
        });
        
        // 点击页面任何地方关闭所有打开的菜单
        document.addEventListener('click', function(e) {
            const openMenus = document.querySelectorAll('.dropdown-menu.show');
            if (openMenus.length > 0) {
                // 检查点击是否在菜单外
                let clickedOutside = true;
                for (let menu of openMenus) {
                    if (menu.contains(e.target) || e.target.classList.contains('dropdown-toggle')) {
                        clickedOutside = false;
                        break;
                    }
                }
                
                // 如果在菜单外点击，关闭所有菜单
                if (clickedOutside) {
                    openMenus.forEach(menu => {
                        menu.classList.remove('show');
                    });
                }
            }
        });
    }
    
    // 添加视觉反馈
    document.querySelectorAll('.dropdown-item, .btn').forEach(item => {
        item.addEventListener('touchstart', function() {
            this.style.opacity = '0.7';
        });
        
        item.addEventListener('touchend', function() {
            this.style.opacity = '';
        });
    });
    
    // 日期选择器优化
    const dateInput = document.getElementById('date');
    if (dateInput) {
        // 添加移动端日期选择优化
        if (isMobile) {
            dateInput.classList.add('mobile-date-input');
        }
        
        dateInput.addEventListener('change', function() {
            // 显示加载中提示
            const loadingOverlay = document.createElement('div');
            loadingOverlay.className = 'position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center bg-white bg-opacity-75';
            loadingOverlay.style.zIndex = '9999';
            
            const spinner = document.createElement('div');
            spinner.className = 'spinner-border text-primary';
            spinner.setAttribute('role', 'status');
            
            const spinnerText = document.createElement('span');
            spinnerText.className = 'ms-2';
            spinnerText.textContent = '数据加载中...';
            
            const spinnerContainer = document.createElement('div');
            spinnerContainer.className = 'd-flex align-items-center';
            spinnerContainer.appendChild(spinner);
            spinnerContainer.appendChild(spinnerText);
            
            loadingOverlay.appendChild(spinnerContainer);
            document.body.appendChild(loadingOverlay);
            
            // 提交表单
            this.form.submit();
        });
    }
    
    // 优化表格显示
    function enhanceTablesDisplay() {
        // 检查是否有空表格，添加"暂无数据"提示
        document.querySelectorAll('table tbody').forEach(tbody => {
            // 如果没有数据行或只有空行
            if (tbody.children.length === 0 || 
                (tbody.children.length === 1 && tbody.children[0].innerText.trim() === '')) {
                
                const noDataRow = document.createElement('tr');
                const noDataCell = document.createElement('td');
                const colspan = tbody.parentElement.querySelector('thead tr th').length || 3;
                
                noDataCell.setAttribute('colspan', colspan);
                noDataCell.className = 'text-center text-muted py-4';
                noDataCell.textContent = '暂无数据';
                
                noDataRow.appendChild(noDataCell);
                tbody.innerHTML = '';
                tbody.appendChild(noDataRow);
            }
        });
        
        // 确保表格内容格式一致
        document.querySelectorAll('table td, table th').forEach(cell => {
            // 为价格和金额添加样式
            if (cell.textContent.includes('¥') || /^\d+\.\d{2}$/.test(cell.textContent.trim())) {
                cell.classList.add('text-end');
            }
            
            // 为数字添加样式
            if (/^\d+(\.\d+)?$/.test(cell.textContent.trim()) && !cell.textContent.includes('¥')) {
                cell.classList.add('text-center');
            }
        });
    }
    
    // 初始化各种增强
    enhanceDropdowns();
    
    // 页面加载完成后再执行一些优化
    window.addEventListener('load', function() {
        enhanceTablesDisplay();
        
        // 在移动设备上优化输入体验
        if (isMobile) {
            // 输入框获得焦点时，确保不被键盘遮挡
            document.querySelectorAll('input, select, textarea').forEach(input => {
                input.addEventListener('focus', function() {
                    // 等待键盘弹出
                    setTimeout(() => {
                        // 滚动到视图中
                        this.scrollIntoView({
                            behavior: 'smooth',
                            block: 'center'
                        });
                    }, 300);
                });
            });
            
            // 标签页切换增强
            document.querySelectorAll('.nav-tabs .nav-link').forEach(tab => {
                tab.addEventListener('click', function() {
                    // 添加点击反馈
                    this.style.backgroundColor = 'rgba(13, 110, 253, 0.1)';
                    setTimeout(() => {
                        this.style.backgroundColor = '';
                    }, 200);
                });
            });
        }
    });
}); 