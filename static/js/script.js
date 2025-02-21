document.addEventListener("DOMContentLoaded", () => {
  const categoriesContainer = document.getElementById("emoji-categories");
  const addCategoryForm = document.getElementById("add-category-form");

  // 获取表情包数据和描述
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

      const description = tagDescriptions[category] || `请添加描述`;
      const titleDiv = document.createElement("div");
      titleDiv.className = "category-title";
      titleDiv.innerHTML = `
            <div class="category-header">
                <div class="category-name" id="category-name-${category}">${category}</div>
                <div class="category-actions">
                    <button class="edit-category-btn" onclick="editCategory('${category}')">编辑类别</button>
                    <button class="delete-category-btn" data-category="${category}">删除类别</button>
                </div>
            </div>
            <div class="category-edit-form" id="category-edit-${category}" style="display: none;">
                <input type="text" class="category-name-input" value="${category}" placeholder="类别名称">
                <input type="text" class="category-desc-input" value="${description}" placeholder="类别描述">
                <div class="edit-buttons">
                    <button class="save-edit-btn" onclick="saveCategory('${category}')">保存</button>
                    <button class="cancel-edit-btn" onclick="cancelEdit('${category}')">取消</button>
                </div>
            </div>
            <p class="description" id="category-desc-${category}">${description}</p>
        `;
      categoryDiv.appendChild(titleDiv);

      // 添加删除类别按钮的事件监听器
      const deleteBtn = titleDiv.querySelector(".delete-category-btn");
      deleteBtn.addEventListener("click", () => deleteCategory(category));

      const emojiGrid = document.createElement("div");
      emojiGrid.className = "emoji-grid";
      emojiGrid.style.display = "flex";
      emojiGrid.style.flexWrap = "wrap";
      emojiGrid.style.gap = "10px";
      emojiGrid.style.padding = "10px";

      // 确保 emojis 是数组
      if (Array.isArray(emojis)) {
        emojis.forEach((emoji) => {
          const emojiItem = document.createElement("div");
          emojiItem.className = "emoji-item";
          emojiItem.style.width = "150px";
          emojiItem.style.height = "150px";
          emojiItem.style.backgroundSize = "contain";
          emojiItem.style.backgroundPosition = "center";
          emojiItem.style.backgroundRepeat = "no-repeat";
          emojiItem.style.cursor = "pointer";
          emojiItem.style.border = "1px solid #ddd";
          emojiItem.style.borderRadius = "4px";
          emojiItem.style.flexShrink = "0";
          emojiItem.style.position = "relative";

          // 添加删除按钮
          const deleteBtn = document.createElement("button");
          deleteBtn.className = "delete-btn";
          deleteBtn.innerHTML = "×";
          deleteBtn.onclick = (e) => {
            e.stopPropagation();
            deleteEmoji(category, emoji);
          };
          emojiItem.appendChild(deleteBtn);

          // 使用 data-bg 存储图片URL
          emojiItem.setAttribute("data-bg", `/memes/${category}/${emoji}`);
          emojiGrid.appendChild(emojiItem);
        });
      }

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
      observer.observe(item);
    });

    // 添加编辑描述的事件监听器
    setupEditDescriptionHandlers();
  }

  // 更新侧边栏目录
  function updateSidebar(data, tagDescriptions) {
    const sidebarList = document.getElementById("sidebar-list");
    if (!sidebarList) return;
    sidebarList.innerHTML = "";

    for (const category in data) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "#category-" + category;
      a.textContent = category; // 只显示类别名称
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
      const data = await response.json();
      if (!response.ok) {
        console.error("添加表情包失败，响应异常");
        alert(data.message);
        return;
      }
      fetchEmojis(); // 刷新表情包列表
      alert(`添加表情包成功: ${data.filename} 到类别 ${data.category}`);
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
      const data = await response.json();
      if (!response.ok) {
        console.error("删除表情包失败，响应异常");
        alert(data.message);
        return;
      }
      fetchEmojis(); // 刷新表情包列表
      alert(`删除表情包成功: ${data.filename} 从类别 ${data.category}`);
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

  // 添加分类相关的事件处理
  document
    .getElementById("add-category-btn")
    .addEventListener("click", function () {
      document.getElementById("add-category-form").style.display = "block";
      this.style.display = "none";
    });

  document
    .getElementById("save-category-btn")
    .addEventListener("click", function () {
      const categoryName = document.getElementById("new-category-name").value;
      const categoryDesc =
        document.getElementById("new-category-description").value ||
        "请添加描述";

      if (!categoryName) {
        alert("请输入类别名称");
        return;
      }

      fetch("/api/category/restore", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          category: categoryName,
          description: categoryDesc,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.message.includes("successfully")) {
            alert("添加类别成功！");
            document.getElementById("new-category-name").value = "";
            document.getElementById("new-category-description").value = "";
            document.getElementById("add-category-form").style.display = "none";
            document.getElementById("add-category-btn").style.display = "block";
            loadCategories(); // 重新加载类别列表
          } else {
            alert("添加类别失败：" + data.message);
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          alert("添加类别失败：" + error);
        });
    });

  // 添加编辑描述的处理函数
  function setupEditDescriptionHandlers() {
    const editButtons = document.querySelectorAll(".edit-description-btn");
    editButtons.forEach((button) => {
      button.addEventListener("click", async (e) => {
        const category = e.target.dataset.category;
        const descriptionElement =
          e.target.parentElement.querySelector(".description");
        const currentDescription = descriptionElement.textContent;

        const newDescription = prompt("请输入新的描述:", currentDescription);
        if (newDescription && newDescription !== currentDescription) {
          try {
            const response = await fetch("/api/category/update_description", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                tag: category,
                description: newDescription,
              }),
            });

            if (!response.ok) throw new Error("更新描述失败");

            // 更新成功后刷新数据
            fetchEmojis();
          } catch (error) {
            console.error("更新描述失败:", error);
            alert("更新描述失败: " + error.message);
          }
        }
      });
    });
  }

  // 检查同步状态的函数
  async function checkSyncStatus() {
    const statusDiv = document.getElementById("sync-status");
    if (!statusDiv) return;

    try {
      const response = await fetch("/api/sync/status");
      if (!response.ok) throw new Error("检查同步状态失败");

      const data = await response.json();
      if (data.error) {
        statusDiv.innerHTML = `<p style="color: red;">${data.detail}</p>`;
        return;
      }

      // 更新状态显示
      let statusHtml = "";
      const { to_add, to_remove } = data.differences;

      if (to_add.length > 0) {
        statusHtml += `
          <div class="status-section">
            <h4>新增类别（需要添加到配置）：</h4>
            <ul>
              ${to_add.map((category) => `<li>${category}</li>`).join("")}
            </ul>
          </div>
        `;
      }

      if (to_remove.length > 0) {
        statusHtml += `
          <div class="status-section">
            <h4>已删除的类别（配置中仍存在）：</h4>
            <ul>
              ${to_remove.map((category) => `<li>${category}</li>`).join("")}
            </ul>
          </div>
        `;
      }

      // 添加图床同步状态显示
      const { img_sync } = data;
      const { to_upload, to_download } = img_sync;

      let syncStatusHtml = "<h4>图床同步状态：</h4>";
      if (to_upload.length > 0) {
        syncStatusHtml += `
          <div>
            <h5>待上传文件：</h5>
            <ul>
              ${to_upload.map((file) => `<li>${file.filename}</li>`).join("")}
            </ul>
          </div>
        `;
      }

      if (to_download.length > 0) {
        syncStatusHtml += `
          <div>
            <h5>待下载文件：</h5>
            <ul>
              ${to_download.map((file) => `<li>${file.filename}</li>`).join("")}
            </ul>
          </div>
        `;
      }

      if (!to_upload.length && !to_download.length) {
        syncStatusHtml += "<p>图床同步状态正常，无需上传或下载文件。</p>";
      }

      statusDiv.innerHTML = statusHtml + syncStatusHtml;
    } catch (error) {
      console.error("检查同步状态失败:", error);
      statusDiv.innerHTML = `
        <p style="color: red;">检查同步状态失败: ${error.message}</p>
        <button onclick="checkSyncStatus()" class="retry-btn">重试</button>
      `;
    }
  }

  // 在同步完成后调用 checkSyncStatus
  async function syncToRemote() {
    try {
      const response = await fetch("/api/sync/upload", {
        method: "POST",
      });
      const data = await response.json();
      if (!response.ok) {
        alert(`同步到云端失败: ${data.message}`);
        return;
      }
      alert("正在同步到云端...");
      checkSyncStatus(); // 检查同步状态
    } catch (error) {
      console.error("同步到云端失败:", error);
      alert("同步到云端失败: " + error.message);
    }
  }

  async function syncFromRemote() {
    try {
      const response = await fetch("/api/sync/download", {
        method: "POST",
      });
      const data = await response.json();
      if (!response.ok) {
        alert(`从云端同步失败: ${data.message}`);
        return;
      }
      alert("正在从云端同步...");
      checkSyncStatus(); // 检查同步状态
    } catch (error) {
      console.error("从云端同步失败:", error);
      alert("从云端同步失败: " + error.message);
    }
  }

  // 添加事件监听器
  document
    .getElementById("upload-sync-btn")
    .addEventListener("click", syncToRemote);
  document
    .getElementById("download-sync-btn")
    .addEventListener("click", syncFromRemote);

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

  // 恢复类别
  async function restoreCategory(category) {
    try {
      const response = await fetch("/api/category/restore", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ category }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.message);

      // 重新加载数据
      await fetchEmojis();
      await checkSyncStatus();
      alert(`恢复类别成功: ${category} 描述: ${data.description}`);
    } catch (error) {
      console.error("恢复类别失败:", error);
      alert("恢复类别失败: " + error.message);
    }
  }

  // 从配置中删除类别
  async function removeFromConfig(category) {
    if (!confirm(`确定要从配置中删除 "${category}" 类别吗？`)) {
      return;
    }

    try {
      const response = await fetch("/api/category/remove_from_config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ category }),
      });

      if (!response.ok) throw new Error("从配置中删除类别失败");

      // 重新加载数据
      await checkSyncStatus();
    } catch (error) {
      console.error("从配置中删除类别失败:", error);
      alert("从配置中删除类别失败: " + error.message);
    }
  }

  // 编辑类别
  function editCategory(category) {
    const nameDisplay = document.getElementById(`category-name-${category}`);
    const descDisplay = document.getElementById(`category-desc-${category}`);
    const editForm = document.getElementById(`category-edit-${category}`);

    nameDisplay.parentElement.style.display = "none";
    descDisplay.style.display = "none";
    editForm.style.display = "block";
  }

  // 取消编辑
  function cancelEdit(category) {
    const nameDisplay = document.getElementById(`category-name-${category}`);
    const descDisplay = document.getElementById(`category-desc-${category}`);
    const editForm = document.getElementById(`category-edit-${category}`);

    nameDisplay.parentElement.style.display = "flex";
    descDisplay.style.display = "block";
    editForm.style.display = "none";
  }

  // 保存类别修改
  async function saveCategory(oldName) {
    const editForm = document.getElementById(`category-edit-${oldName}`);
    const newName = editForm.querySelector(".category-name-input").value.trim();
    const newDesc = editForm.querySelector(".category-desc-input").value.trim();

    try {
      // 如果名称有变化，先重命名类别
      if (oldName !== newName) {
        const renameResponse = await fetch("/api/category/rename", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ old_name: oldName, new_name: newName }),
        });
        if (!renameResponse.ok) throw new Error("重命名类别失败");
      }

      // 更新描述
      const descResponse = await fetch("/api/category/update_description", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag: newName, description: newDesc }),
      });
      if (!descResponse.ok) throw new Error("更新描述失败");

      // 重新加载数据
      await fetchEmojis();
    } catch (error) {
      console.error("保存类别修改失败:", error);
      alert("保存类别修改失败: " + error.message);
    }
  }

  // 确保这些函数是全局可访问的
  window.restoreCategory = restoreCategory;
  window.removeFromConfig = removeFromConfig;
  window.syncConfig = syncConfig;
  window.editCategory = editCategory;
  window.cancelEdit = cancelEdit;
  window.saveCategory = saveCategory;

  // 初始化加载数据
  fetchEmojis();

  // 同步配置
  syncConfig();

  // 加载类别数据并更新显示
  async function loadCategories() {
    try {
      const response = await fetch("/api/emotions");
      if (!response.ok) {
        throw new Error("无法加载类别数据");
      }
      const data = await response.json();

      // 确保 data 是一个对象
      if (typeof data !== "object" || Array.isArray(data)) {
        throw new Error("返回的数据格式不正确");
      }

      updateSidebar(data, data); // 假设 data 也包含描述
      displayCategories(data, data); // 更新类别显示
    } catch (error) {
      console.error("加载类别失败:", error);
      alert("加载类别失败: " + error.message);
    }
  }

  // 在 DOMContentLoaded 事件中调用 loadCategories
  loadCategories(); // 页面加载时获取类别

  // 在页面加载时自动检查同步状态
  checkSyncStatus();

  document
    .getElementById("check-sync-btn")
    .addEventListener("click", checkSyncStatus);
});
