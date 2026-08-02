import { createPinia } from 'pinia'
import { createApp } from 'vue'
import { ElDialog, ElInput, ElLoading, ElTabPane, ElTabs } from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import './styles.css'

createApp(App)
  .use(createPinia())
  .use(router)
  .use(ElDialog)
  .use(ElInput)
  .use(ElLoading)
  .use(ElTabPane)
  .use(ElTabs)
  .mount('#app')
