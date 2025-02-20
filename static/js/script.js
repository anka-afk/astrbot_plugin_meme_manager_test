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
    const maxRetries = 10; // 增加最大重试次数
    const baseDelay = 2000; // 基础延迟时间（毫秒）
    let retryCount = parseInt(emojiItem.dataset.retryCount || "0");

    if (retryCount < maxRetries) {
      // 增加重试计数
      retryCount++;
      emojiItem.dataset.retryCount = retryCount;

      // 使用指数退避策略计算延迟时间
      const delay = Math.min(baseDelay * Math.pow(1.5, retryCount - 1), 10000);

      // 延迟后重试加载
      setTimeout(() => {
        console.log(
          `重试加载图片 (${retryCount}/${maxRetries}), 延迟: ${delay}ms`
        );
        const bgUrl = emojiItem.getAttribute("data-bg");
        emojiItem.style.backgroundImage = `url('${bgUrl}?retry=${retryCount}')`;
      }, delay);
    } else {
      // 达到最大重试次数，显示错误状态
      emojiItem.classList.add("image-load-error");
      emojiItem.style.backgroundImage = "none";
      emojiItem.innerHTML += '<div class="error-overlay">加载失败</div>';
    }
  }

  // 根据数据生成 DOM 节点，展示每个分类及其表情包，并添加上传块
  function displayCategories(data, tagDescriptions) {
    if (!categoriesContainer) return;
    categoriesContainer.innerHTML = "";

    for (const category in data) {
      const categoryDiv = document.createElement("div");
      categoryDiv.classList.add("category");
      categoryDiv.id = "category-" + category;

      // 标题和按钮容器
      const headerDiv = document.createElement("div");
      headerDiv.style.display = "flex";
      headerDiv.style.justifyContent = "space-between";
      headerDiv.style.alignItems = "flex-start";
      headerDiv.style.width = "100%";

      // 左侧：标题、描述和编辑按钮
      const leftDiv = document.createElement("div");
      leftDiv.style.display = "flex";
      leftDiv.style.flexDirection = "column";
      leftDiv.style.gap = "10px";

      // 标题行
      const titleRow = document.createElement("div");
      titleRow.style.display = "flex";
      titleRow.style.alignItems = "center";
      titleRow.style.gap = "10px";

      // 分类标题
      const categoryTitle = document.createElement("h3");
      categoryTitle.style.margin = "0";
      categoryTitle.textContent = category;

      // 编辑按钮
      const editButton = document.createElement("button");
      editButton.classList.add("edit-category-btn");
      editButton.textContent = "编辑描述";

      titleRow.appendChild(categoryTitle);
      titleRow.appendChild(editButton);

      // 描述文本
      const descriptionText = document.createElement("p");
      descriptionText.classList.add("category-description");
      descriptionText.style.margin = "0";
      descriptionText.style.color = "#666";
      descriptionText.style.fontSize = "0.9em";
      const description =
        tagDescriptions[category] || `未添加描述的${category}类别`;
      descriptionText.textContent = description;

      leftDiv.appendChild(titleRow);
      leftDiv.appendChild(descriptionText);

      editButton.onclick = () => {
        const existingEdit = categoryDiv.querySelector(
          ".edit-category-container"
        );
        if (existingEdit) {
          existingEdit.remove();
          return;
        }

        const editContainer = document.createElement("div");
        editContainer.classList.add("edit-category-container");

        const input = document.createElement("input");
        input.type = "text";
        input.value = description;
        input.placeholder = "请输入类别描述";

        const saveBtn = document.createElement("button");
        saveBtn.textContent = "保存";
        saveBtn.onclick = async () => {
          const newDescription = input.value.trim();
          if (newDescription) {
            try {
              const response = await fetch("/api/category/update_description", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  tag: category,
                  description: newDescription,
                }),
              });
              if (!response.ok) {
                throw new Error("更新描述失败");
              }
              // 重新加载数据
              fetchEmojis();
            } catch (error) {
              console.error("更新描述失败:", error);
              alert("更新描述失败: " + error.message);
            }
          }
        };

        editContainer.appendChild(input);
        editContainer.appendChild(saveBtn);
        leftDiv.appendChild(editContainer);
      };

      // 右侧：删除按钮
      const deleteCategoryBtn = document.createElement("button");
      deleteCategoryBtn.classList.add("delete-category-btn");
      deleteCategoryBtn.textContent = "删除分类";
      deleteCategoryBtn.addEventListener("click", () =>
        deleteCategory(category)
      );

      headerDiv.appendChild(leftDiv);
      headerDiv.appendChild(deleteCategoryBtn);
      categoryDiv.appendChild(headerDiv);

      // 创建表情列表容器
      const emojiListDiv = document.createElement("div");
      emojiListDiv.classList.add("emoji-list");

      // 遍历已有表情包
      data[category].forEach((emoji) => {
        const emojiItem = document.createElement("div");
        emojiItem.classList.add("emoji-item");

        // 创建实际的图片元素
        const img = new Image();
        img.style.display = "none"; // 先隐藏图片

        // 设置加载超时（增加到15秒）
        const timeoutId = setTimeout(() => {
          img.src = ""; // 取消加载
          handleImageError(emojiItem);
        }, 15000);

        img.onload = () => {
          clearTimeout(timeoutId);
          emojiItem.style.backgroundImage = `url('${img.src}')`;
          img.remove(); // 移除临时图片元素
        };

        img.onerror = () => {
          clearTimeout(timeoutId);
          handleImageError(emojiItem);
          img.remove(); // 移除临时图片元素
        };

        const imgUrl = `/memes/${category}/${emoji}`;
        emojiItem.setAttribute("data-bg", imgUrl);
        img.src = imgUrl;
        emojiItem.appendChild(img);

        // 删除按钮（右上角）
        const deleteBtn = document.createElement("button");
        deleteBtn.classList.add("delete-btn");
        deleteBtn.textContent = "×";
        deleteBtn.addEventListener("click", () => deleteEmoji(category, emoji));
        emojiItem.appendChild(deleteBtn);

        emojiListDiv.appendChild(emojiItem);
      });

      // 上传块：拖拽或点击上传新的表情包
      const uploadBlock = document.createElement("div");
      uploadBlock.classList.add("upload-emoji");
      uploadBlock.textContent = "拖拽或点击上传";

      // 隐藏的文件输入
      const fileInput = document.createElement("input");
      fileInput.type = "file";
      fileInput.accept = "image/*";
      fileInput.style.display = "none";
      uploadBlock.appendChild(fileInput);

      // 点击上传块打开文件选择对话框
      uploadBlock.addEventListener("click", () => {
        fileInput.click();
      });
      // 文件选择后上传
      fileInput.addEventListener("change", () => {
        if (fileInput.files && fileInput.files[0]) {
          uploadEmoji(category, fileInput.files[0]);
        }
      });
      // 拖拽事件
      uploadBlock.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadBlock.classList.add("dragover");
      });
      uploadBlock.addEventListener("dragleave", (e) => {
        e.preventDefault();
        uploadBlock.classList.remove("dragover");
      });
      uploadBlock.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadBlock.classList.remove("dragover");
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          uploadEmoji(category, e.dataTransfer.files[0]);
        }
      });

      emojiListDiv.appendChild(uploadBlock);
      categoryDiv.appendChild(emojiListDiv);
      categoriesContainer.appendChild(categoryDiv);
    }

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
