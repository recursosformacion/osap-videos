CREATE TABLE IF NOT EXISTS youtube_videos (
  video_id VARCHAR(32) PRIMARY KEY,
  url VARCHAR(512) NOT NULL,
  title VARCHAR(512) NOT NULL,
  channel VARCHAR(255) NULL,
  material_type VARCHAR(32) NULL,
  created_at DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS resource_youtube_videos (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  resource_id VARCHAR(128) NOT NULL,
  work_id VARCHAR(128) NOT NULL,
  video_id VARCHAR(32) NOT NULL,
  voice VARCHAR(16) NOT NULL,
  search_query VARCHAR(512) NULL,
  similarity DECIMAL(5,4) NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY uq_resource_video_voice (resource_id, video_id, voice),
  KEY ix_work (work_id),
  CONSTRAINT fk_ryv_video FOREIGN KEY (video_id) REFERENCES youtube_videos(video_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS resource_youtube_votes (
  user_id VARCHAR(64) NOT NULL,
  resource_id VARCHAR(128) NOT NULL,
  video_id VARCHAR(32) NOT NULL,
  voice VARCHAR(16) NOT NULL,
  decision ENUM('approved','rejected') NOT NULL,
  note VARCHAR(512) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (user_id, resource_id, video_id, voice),
  KEY ix_video (video_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

