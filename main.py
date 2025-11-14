# import os
# from dotenv import load_dotenv

# from app.services.exa_service import PerplexitySearchService


# load_dotenv()


# def main() -> None:
#     api_key = os.getenv('PERPLEXITY_API_KEY')
#     if not api_key:
#         raise SystemExit('Set PERPLEXITY_API_KEY in your environment before running this script.')

#     service = PerplexitySearchService(api_key=api_key)

#     query = input('Enter your research query: ').strip()
#     if not query:
#         print('No query provided. Exiting.')
#         return

#     results = service.search(query=query, num_results=5)

#     answer = results.get('answer')
#     if answer:
#         print('\n=== Summary ===')
#         print(answer)

#     print('\n=== Sources ===')
#     for idx, result in enumerate(results.get('results', []), start=1):
#         title = result.get('title') or f'Result {idx}'
#         url = result.get('url') or 'No URL provided'
#         print(f"{idx}. {title}\n   {url}\n")


# if __name__ == '__main__':
#     main()