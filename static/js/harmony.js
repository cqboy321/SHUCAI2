/**
 * 华为鸿蒙系统优化脚本
 * HarmonyOS Optimization Script
 */

document.addEventListener('DOMContentLoaded', function() {
    // 检测是否是鸿蒙系统
    const isHarmonyOS = /HarmonyOS|EMUI|HUAWEI|HiSilicon/i.test(navigator.userAgent);
    
    if (isHarmonyOS) {
        document.documentElement.classList.add('harmony-os');
        document.body.classList.add('harmony-os');
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
    
    // ===== 新增：下拉菜单交互增强 =====
    
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
                if (window.innerWidth < 769) {
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
    
    // 初始化下拉菜单增强
    enhanceDropdowns();

    // 添加视觉反馈
    document.querySelectorAll('.dropdown-item').forEach(item => {
        item.addEventListener('touchstart', function() {
            this.style.backgroundColor = 'rgba(13, 110, 253, 0.1)';
        });
        
        item.addEventListener('touchend', function() {
            this.style.backgroundColor = '';
        });
    });
    
    // ===== 新增：汇总卡片优化 =====
    
    // 优化汇总卡片表格显示
    function enhanceSummaryCards() {
        // 检查是否有数据，没有数据则显示提示
        document.querySelectorAll('.card .card .table-sm tbody').forEach(tableBody => {
            if (tableBody.children.length === 0) {
                const noDataRow = document.createElement('tr');
                const noDataCell = document.createElement('td');
                noDataCell.setAttribute('colspan', '3');
                noDataCell.className = 'text-center text-muted';
                noDataCell.textContent = '暂无数据';
                noDataRow.appendChild(noDataCell);
                tableBody.appendChild(noDataRow);
            }
        });
        
        // 确保表格适应容器宽度
        document.querySelectorAll('.card .card .table-responsive').forEach(tableContainer => {
            const table = tableContainer.querySelector('table');
            if (table) {
                // 确保表格列宽适当
                const headerCells = table.querySelectorAll('th');
                if (headerCells.length > 0) {
                    // 设置平均宽度
                    const width = 100 / headerCells.length;
                    headerCells.forEach(cell => {
                        cell.style.width = `${width}%`;
                    });
                }
            }
        });
        
        // 在移动设备上添加横向滚动提示
        if (window.innerWidth < 769) {
            document.querySelectorAll('.card .card .table-responsive').forEach(container => {
                if (container.scrollWidth > container.clientWidth) {
                    // 如果表格超出容器宽度，添加视觉提示
                    container.classList.add('has-scroll');
                    
                    // 添加滑动手势监听
                    container.addEventListener('touchstart', function(e) {
                        this.dataset.touchStartX = e.touches[0].clientX;
                    }, { passive: true });
                    
                    container.addEventListener('touchmove', function(e) {
                        if (this.dataset.touchStartX) {
                            const moveX = e.touches[0].clientX - this.dataset.touchStartX;
                            if (Math.abs(moveX) > 10) {
                                e.stopPropagation();
                            }
                        }
                    }, { passive: true });
                }
            });
        }
    }
    
    // 初始化汇总卡片优化
    setTimeout(enhanceSummaryCards, 100);
    
    // 添加日期选择器优化
    const dateInput = document.getElementById('date');
    if (dateInput) {
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
}); 