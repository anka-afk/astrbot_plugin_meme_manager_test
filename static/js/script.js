document.addEventListener("DOMContentLoaded", () => {
  const categoriesContainer = document.getElementById("emoji-categories");
  const addCategoryForm = document.getElementById("add-category-form");

  // 获取中文-英文映射
  async function fetchEmotions() {
    try {
      const response = await fetch("/api/emotions");
      if (!response.ok) throw new Error("响应异常");
      return await response.json();
    } catch (error) {
      console.error("加载 emotions.json 失败", error);
      return {};
    }
  }

  // 获取所有表情包数据
  async function fetchEmojis() {
    try {
      const [emojiResponse, tagDescriptions] = await Promise.all([
        fetch("/api/emoji").then((res) => {
          if (!res.ok) throw new Error("获取表情包数据失败");
          return res.json();
        }),
        fetch("/api/emotions").then((res) => {
          if (!res.ok) throw new Error("获取标签描述失败");
          return res.json();
        }),
      ]);
      displayCategories(emojiResponse, tagDescriptions);
      updateSidebar(emojiResponse, tagDescriptions);
    } catch (error) {
      console.error("加载表情包数据失败", error);
    }
  }

  // 反向查找中文名称
  function getChineseName(emotionMap, category) {
    for (const [chinese, english] of Object.entries(emotionMap)) {
      if (english === category) {
        return chinese;
      }
    }
    return category;
  }

  // 修改图片加载错误处理函数
  function handleImageError(emojiItem) {
    const img = emojiItem.querySelector("img");
    const errorDiv = document.createElement("div");
    errorDiv.className = "error-placeholder";
    errorDiv.textContent = "图片加载失败";
    img.replaceWith(errorDiv);
  }

  // 根据数据生成 DOM 节点，展示每个分类及其表情包，并添加上传块
  function displayCategories(emojiData, tagDescriptions) {
    const container = document.getElementById("emoji-categories");
    container.innerHTML = "";

    Object.entries(emojiData).forEach(([category, emojis]) => {
      const categoryDiv = document.createElement("div");
      categoryDiv.className = "category";
      categoryDiv.id = `category-${category}`;

      const description =
        tagDescriptions[category] || `未添加描述的${category}类别`;
      const titleDiv = document.createElement("div");
      titleDiv.className = "category-title";
      titleDiv.innerHTML = `
        <h2>${category}</h2>
        <p class="description">${description}</p>
        <button class="edit-description-btn" data-category="${category}">
          编辑描述
        </button>
      `;
      categoryDiv.appendChild(titleDiv);

      const emojiGrid = document.createElement("div");
      emojiGrid.className = "emoji-grid";

      emojis.forEach((emoji) => {
        const emojiItem = document.createElement("div");
        emojiItem.className = "emoji-item";
        // 设置样式以保持原有的布局
        emojiItem.style.width = "150px";
        emojiItem.style.height = "150px";
        emojiItem.style.backgroundSize = "contain";
        emojiItem.style.backgroundPosition = "center";
        emojiItem.style.backgroundRepeat = "no-repeat";
        emojiItem.style.margin = "5px";
        emojiItem.style.cursor = "pointer";
        emojiItem.style.border = "1px solid #ddd";
        emojiItem.style.borderRadius = "4px";

        // 使用 data-bg 存储图片URL
        emojiItem.setAttribute("data-bg", `/memes/${category}/${emoji}`);
        emojiGrid.appendChild(emojiItem);
      });

      categoryDiv.appendChild(emojiGrid);
      container.appendChild(categoryDiv);
    });

    // 懒加载背景图片
    const lazyBackgrounds = document.querySelectorAll(".emoji-item");

    const observer = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const emojiItem = entry.target;
            const bgUrl = emojiItem.getAttribute("data-bg");
            emojiItem.style.backgroundImage = `url('${bgUrl}')`; // 加载背景图片
            emojiItem.removeAttribute("data-bg"); // 移除临时属性
            observer.unobserve(emojiItem); // 停止观察
          }
        });
      },
      { threshold: 0.1 }
    );

    lazyBackgrounds.forEach((item) => {
      observer.observe(item); // 观察每个表情包
    });

    // 添加编辑描述的事件监听器
    setupEditDescriptionHandlers();
  }

  // 更新侧边栏目录，根据分类数据生成跳转链接
  function updateSidebar(data, tagDescriptions) {
    const sidebarList = document.getElementById("sidebar-list");
    if (!sidebarList) return;
    sidebarList.innerHTML = "";

    for (const category in data) {
      const li = document.createElement("li");
      const description =
        tagDescriptions[category] || `未添加描述的${category}类别`;
      const a = document.createElement("a");
      a.href = "#category-" + category;
      a.innerHTML = `${category}<br><small style="color: #666">${description}</small>`;
      li.appendChild(a);
      sidebarList.appendChild(li);
    }
  }

  // 上传表情包
  async function uploadEmoji(category, file) {
    const formData = new FormData();
    formData.append("category", category);
    formData.append("image_file", file);

    try {
      const response = await fetch("/api/emoji/add", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        console.error("添加表情包失败，响应异常");
      }
      fetchEmojis();
    } catch (error) {
      console.error("添加表情包失败", error);
    }
  }

  // 删除表情包
  async function deleteEmoji(category, emoji) {
    if (!confirm("是否删除该表情包？")) return;
    if (!confirm("请再次确认删除该表情包，此操作不可恢复！")) return;
    try {
      const response = await fetch("/api/emoji/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category, image_file: emoji }),
      });
      if (!response.ok) {
        console.error("删除表情包失败，响应异常");
      }
      fetchEmojis();
    } catch (error) {
      console.error("删除表情包失败", error);
    }
  }

  // 删除表情包类别
  async function deleteCategory(category) {
    if (
      !confirm(
        `确定要删除分类 "${category}" 吗？这将同时删除配置文件中的映射关系。`
      )
    ) {
      return;
    }

    try {
      const response = await fetch("/api/category/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category }),
      });

      if (!response.ok) {
        throw new Error("删除分类失败");
      }

      // 重新加载数据
      fetchEmojis();
    } catch (error) {
      console.error("删除分类失败:", error);
      alert("删除分类失败: " + error.message);
    }
  }

  // 添加分类：通过新表单输入中文名称和英文名称
  const addCategoryBtn = document.getElementById("add-category-btn");
  if (addCategoryBtn && addCategoryForm) {
    addCategoryBtn.addEventListener("click", () => {
      addCategoryForm.style.display = "block";
    });
  }
  const saveCategoryBtn = document.getElementById("save-category-btn");
  if (saveCategoryBtn) {
    saveCategoryBtn.addEventListener("click", async () => {
      const chineseInput = document.getElementById("new-category-chinese");
      const englishInput = document.getElementById("new-category-english");
      const chineseName = chineseInput?.value.trim();
      const englishName = englishInput?.value.trim();
      if (chineseName && englishName) {
        try {
          const response = await fetch("/api/category/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chinese: chineseName,
              english: englishName,
            }),
          });
          if (!response.ok) {
            console.error("添加分类失败，响应异常");
          }
          addCategoryForm.style.display = "none";
          // 清空输入框
          chineseInput.value = "";
          englishInput.value = "";
          fetchEmojis();
        } catch (error) {
          console.error("添加分类失败", error);
        }
      }
    });
  }

  // 修改检查同步状态的函数
  async function checkSyncStatus() {
    const statusDiv = document.getElementById("sync-status");
    if (!statusDiv) return;

    try {
      const response = await fetch("/api/sync/status");
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "检查同步状态失败");
      }
      const status = await response.json();

      // 更新状态显示
      let statusHtml = "";
      if (status.to_upload && status.to_upload.length > 0) {
        statusHtml += "<p>待上传文件：</p><ul>";
        status.to_upload.slice(0, 5).forEach((file) => {
          statusHtml += `<li>${file.category}/${file.filename}</li>`;
        });
        if (status.to_upload.length > 5) {
          statusHtml += "<li>...</li>";
        }
        statusHtml += "</ul>";
      }

      if (status.to_download && status.to_download.length > 0) {
        statusHtml += "<p>待下载文件：</p><ul>";
        status.to_download.slice(0, 5).forEach((file) => {
          statusHtml += `<li>${file.category}/${file.filename}</li>`;
        });
        if (status.to_download.length > 5) {
          statusHtml += "<li>...</li>";
        }
        statusHtml += "</ul>";
      }

      if (!statusHtml) {
        statusHtml = "<p>所有文件已同步！</p>";
      }

      statusDiv.innerHTML = statusHtml;
    } catch (error) {
      console.error("检查同步状态失败:", error);
      statusDiv.innerHTML = `
        <p style="color: red;">检查同步状态失败: ${error.message}</p>
        <p>请点击"检查同步状态"按钮手动检查</p>
      `;
    }
  }

  async function syncToRemote() {
    try {
      const btn = document.getElementById("upload-sync-btn");
      btn.disabled = true;
      btn.textContent = "同步中...";

      const response = await fetch("/api/sync/upload", { method: "POST" });
      if (!response.ok) throw new Error("同步到云端失败");

      // 开始轮询检查进度
      while (true) {
        const statusResponse = await fetch("/api/sync/check_process");
        if (!statusResponse.ok) throw new Error("检查同步状态失败");
        const status = await statusResponse.json();

        if (status.completed) {
          if (status.success) {
            alert("同步到云端完成！");
            await checkSyncStatus(); // 刷新同步状态
          } else {
            throw new Error("同步失败");
          }
          break;
        }

        // 等待1秒后再次检查
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } catch (error) {
      console.error("同步到云端失败:", error);
      alert("同步到云端失败: " + error.message);
    } finally {
      const btn = document.getElementById("upload-sync-btn");
      btn.disabled = false;
      btn.textContent = "同步到云端";
    }
  }

  async function syncFromRemote() {
    try {
      const btn = document.getElementById("download-sync-btn");
      btn.disabled = true;
      btn.textContent = "同步中...";

      const response = await fetch("/api/sync/download", { method: "POST" });
      if (!response.ok) throw new Error("从云端同步失败");

      // 开始轮询检查进度
      while (true) {
        const statusResponse = await fetch("/api/sync/check_process");
        if (!statusResponse.ok) throw new Error("检查同步状态失败");
        const status = await statusResponse.json();

        if (status.completed) {
          if (status.success) {
            alert("从云端同步完成！");
            await checkSyncStatus(); // 刷新同步状态
            await fetchEmojis(); // 刷新表情包列表
          } else {
            throw new Error("同步失败");
          }
          break;
        }

        // 等待1秒后再次检查
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    } catch (error) {
      console.error("从云端同步失败:", error);
      alert("从云端同步失败: " + error.message);
    } finally {
      const btn = document.getElementById("download-sync-btn");
      btn.disabled = false;
      btn.textContent = "从云端同步";
    }
  }

  // 添加同步按钮的事件监听器
  document
    .getElementById("check-sync-btn")
    ?.addEventListener("click", checkSyncStatus);
  document
    .getElementById("upload-sync-btn")
    ?.addEventListener("click", syncToRemote);
  document
    .getElementById("download-sync-btn")
    ?.addEventListener("click", syncFromRemote);

  // 初始检查一次同步状态
  checkSyncStatus();

  // 添加同步配置的函数
  async function syncConfig() {
    try {
      const response = await fetch("/api/sync/config", {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error("同步配置失败");
      }
      // 重新加载数据
      await fetchEmojis();
    } catch (error) {
      console.error("同步配置失败:", error);
      alert("同步配置失败: " + error.message);
    }
  }

  // 初始化加载数据
  fetchEmojis();

  // 同步配置
  syncConfig();
});
