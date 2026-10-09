from abc import ABC, abstractmethod


class AbstractPost(ABC):
    @abstractmethod
    def url(self) -> str: ...

    @abstractmethod
    def render(self) -> str: ...

    @abstractmethod
    def photos(self) -> list[str]: ...

    @abstractmethod
    def videos(self) -> list[str]: ...

    @abstractmethod
    def gifs(self) -> list[str]: ...
