# Use Python 3.12 as base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    nodejs \
    npm \
    default-jre \
    maven \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers
RUN npm install -g playwright
RUN npx playwright install

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Install poetry
RUN pip install poetry

# Configure poetry
RUN poetry config virtualenvs.create false

# Install Python dependencies
RUN poetry install --no-dev

# Install Node.js dependencies (if package.json exists)
COPY package*.json ./
RUN if [ -f package.json ]; then npm install; fi

# Copy the application code
COPY src/ ./src/
COPY tests/ ./tests/

# Clone tree-sitter grammars into vendor directory
RUN mkdir -p vendor && \
    git clone https://github.com/tree-sitter/tree-sitter-python.git vendor/tree-sitter-python && \
    git clone https://github.com/tree-sitter/tree-sitter-javascript.git vendor/tree-sitter-javascript && \
    git clone https://github.com/tree-sitter/tree-sitter-java.git vendor/tree-sitter-java

RUN mkdir -p build

# Build tree-sitter parsers
RUN mkdir -p build && python -c "from tree_sitter import Language; Language.build_library('build/my-languages.so', ['vendor/tree-sitter-python', 'vendor/tree-sitter-javascript', 'vendor/tree-sitter-java'])"

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Expose port for potential web interface
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PATH="/app/src:${PATH}"

# Default command
CMD ["ai-test-agent", "--help"]