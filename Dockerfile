# First, specify the base Docker image.
# You can see the Docker images from Apify at https://hub.docker.com/r/apify/.
# You can also use any other image from Docker Hub.
FROM apify/actor-python:3.13
RUN apt update && apt install -yq git && rm -rf /var/lib/apt/lists/*

RUN pip install -U pip setuptools

# Second, copy just requirements.txt into the Actor image,
# since it should be the only file that affects the dependency install in the next step,
# in order to speed up the build
COPY requirements.txt ./

# Install the dependencies
RUN echo "Python version:" \
 && python --version \
 && echo "Installing dependencies:" \
 # Install everything using pip, set playwright version so that it matches whatever is pre-installed in the image
 && cat requirements.txt | \
 # Replace playwright version so that it matches whatever is pre-installed in the image (the `hash` checks if playwright is installed)
    sed "s/^playwright==\(.*\)/playwright==$(hash playwright 2>/dev/null && (playwright --version | cut -d ' ' -f 2) || echo '\1')/" | \
 # Install everything using pip (ignore dependency checks - the lockfile is correct, period)
    pip install -r /dev/stdin --no-dependencies \
 && echo "All installed Python packages:" \
 && pip freeze
# Next, copy the remaining files and directories with the source code.
# Since we do this after installing the dependencies, quick build will be really fast
# for most source file changes.
COPY . ./

# Use compileall to ensure the runnability of the Actor Python code.
RUN python -m compileall -q .

# Specify how to launch the source code of your Actor.
CMD ["python", "-m", "dior_crawler"]
