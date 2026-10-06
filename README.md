# URL Shortener（FastAPI + PostgreSQL + Redis）
## 下載
```
git clone https://github.com/cooloo9871/Shortener.git; cd Shortener
```

## 啟動
```bash
cp .env.example .env            # 修改 DB_PASSWORD，並同步更新 secrets/db_password.txt
docker compose up -d --build
```

## 試用
```bash
# 建立短網址
curl -X POST localhost:8080/links -H 'Content-Type: application/json' \
  -d '{"url":"https://kubernetes.io/docs/"}'

# 轉址（第一次查 DB，之後一小時內都命中 Redis）
curl -I localhost:8080/<code>

# 查看統計
curl localhost:8080/links/<code>/stats
```

## 快取策略
- **Cache-aside**：轉址時先查 Redis，miss 才查 PostgreSQL 並回填（TTL 1 小時）
- **寫入緩衝**：點擊數先在 Redis `INCR`，避免每次轉址都寫 DB；統計時把 DB 值與 Redis 待寫入值相加
- 正式環境可加一個排程服務，定期把 `hits:*` 批次寫回 PostgreSQL
