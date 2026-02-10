<template>
  <div id="app">
    <nav class="navbar">
      <div class="nav-brand">
        <h1>🤖 Nanobot</h1>
      </div>
      <div class="nav-links">
        <router-link to="/dashboard">仪表盘</router-link>
        <router-link to="/accounts">账号池</router-link>
        <router-link to="/config">配置</router-link>
        <router-link to="/chat">对话</router-link>
        <router-link to="/flow">工作流</router-link>
      </div>
    </nav>
    
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
// 应用主入口组件
</script>

<style scoped>
#app {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 2rem;
  background: #2c3e50;
  color: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.nav-brand h1 {
  margin: 0;
  font-size: 1.5rem;
}

.nav-links {
  display: flex;
  gap: 1.5rem;
}

.nav-links a {
  color: white;
  text-decoration: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  transition: background 0.2s;
}

.nav-links a:hover {
  background: rgba(255, 255, 255, 0.1);
}

.nav-links a.router-link-active {
  background: rgba(255, 255, 255, 0.2);
  font-weight: bold;
}

.main-content {
  flex: 1;
  overflow: auto;
  padding: 2rem;
  background: #f5f5f5;
}
</style>
